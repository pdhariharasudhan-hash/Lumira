from collections import Counter
from hashlib import sha256
from pathlib import Path
import re

from fastapi import APIRouter, HTTPException, Query

from app.services.projects.project_discovery_service import ProjectDiscoveryService
from app.services.projects.project_paths import resolve_project_path

router = APIRouter()
IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
MAX_MANIFEST_FILES = 500


def _projects():
    try:
        return ProjectDiscoveryService().get_projects()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Project metadata is unavailable") from exc


def _project_or_404(project_name: str):
    safe_path = resolve_project_path(project_name)
    if safe_path is None or not safe_path.is_dir():
        raise HTTPException(status_code=404, detail="project not found")
    project = next((item for item in _projects() if item.get("project") == project_name), None)
    if project is None:
        raise HTTPException(status_code=404, detail="project metadata not found")
    return safe_path, project


@router.get("/projects/summary")
def project_summary():
    projects = _projects()
    project_types = Counter()
    statuses = Counter()
    version_total = 0
    without_versions = []
    for project in projects:
        versions = int(project.get("versions", 0) or 0)
        version_total += versions
        latest = project.get("latest") if isinstance(project.get("latest"), dict) else {}
        project_types[str(latest.get("project_type") or "unknown")] += 1
        statuses[str(latest.get("status") or "unknown")] += 1
        if versions == 0:
            without_versions.append(project.get("project"))
    return {
        "success": True, "project_count": len(projects), "version_count": version_total,
        "projects_without_valid_versions": without_versions[:100],
        "project_type_counts": dict(project_types.most_common(30)),
        "latest_status_counts": dict(statuses.most_common(30)),
        "projects": [{"project": item.get("project"), "versions": item.get("versions", 0),
                      "latest_version": (item.get("latest") or {}).get("version") if isinstance(item.get("latest"), dict) else None,
                      "status": (item.get("latest") or {}).get("status") if isinstance(item.get("latest"), dict) else None}
                     for item in projects[:200]],
        "truncated": len(projects) > 200,
    }


@router.get("/projects/search")
def search_projects(q: Annotated[str, Query(min_length=1, max_length=200)], limit: Annotated[int, Query(ge=1, le=100)] = 30):
    query = q.strip().casefold()
    if not query:
        raise HTTPException(status_code=422, detail="search query must not be empty")
    matches = []
    for item in _projects():
        latest = item.get("latest") if isinstance(item.get("latest"), dict) else {}
        searchable = " ".join([str(item.get("project") or ""), str(latest.get("idea") or ""),
                               str(latest.get("entity") or ""), str(latest.get("project_type") or ""),
                               str(latest.get("status") or ""), str(latest.get("version") or "")]).casefold()
        if query in searchable:
            matches.append(item)
    return {"success": True, "query": q.strip(), "total": len(matches), "projects": matches[:limit]}


@router.get("/projects/{project_name}/health")
def project_health(project_name: str):
    project_path, project = _project_or_404(project_name)
    versions = ProjectDiscoveryService().get_versions(project_name)
    findings = []
    if not versions:
        findings.append({"code": "no_valid_versions", "severity": "warning"})
    latest = versions[-1] if versions else None
    if latest and not latest.get("status"):
        findings.append({"code": "latest_status_missing", "severity": "warning"})
    if latest and not latest.get("idea"):
        findings.append({"code": "project_description_missing", "severity": "info"})
    manifest_count = 0
    try:
        for path in project_path.iterdir():
            if path.is_dir() and not path.is_symlink() and path.name not in IGNORED_DIRS:
                safe_version = resolve_project_path(project_name, path.name)
                if safe_version is not None and safe_version == path.resolve() and path.name.startswith("v"):
                    manifest_count += 1
    except OSError:
        findings.append({"code": "version_directory_unreadable", "severity": "warning"})
    return {
        "success": True, "project": project_name, "valid_metadata_version_count": len(versions),
        "version_directory_count": manifest_count, "latest_version": latest.get("version") if latest else None,
        "latest_status": latest.get("status") if latest else None, "finding_count": len(findings),
        "findings": findings, "is_healthy": not any(item["severity"] == "warning" for item in findings),
        "metadata": {"project_type": latest.get("project_type") if latest else None,
                     "created": latest.get("created") if latest else None,
                     "metadata_version_count": project.get("versions", 0)},
    }


@router.get("/projects/{project_name}/manifest")
def project_manifest(
    project_name: str,
    version: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_MANIFEST_FILES)] = 200,
):
    project_path, project = _project_or_404(project_name)
    version_name = version or ((project.get("latest") or {}).get("version") if isinstance(project.get("latest"), dict) else None)
    if not isinstance(version_name, str) or not version_name:
        raise HTTPException(status_code=404, detail="project version not found")
    version_path = resolve_project_path(project_name, version_name)
    if version_path is None or not version_path.is_dir() or version_path.parent != project_path:
        raise HTTPException(status_code=404, detail="project version not found")
    files = []
    try:
        for path in version_path.rglob("*"):
            if len(files) >= MAX_MANIFEST_FILES:
                break
            if any(part in IGNORED_DIRS or part.startswith(".") for part in path.relative_to(version_path).parts):
                continue
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(version_path.resolve()):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            files.append({"path": path.relative_to(version_path).as_posix(), "size_bytes": size})
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Project file manifest is unavailable") from exc
    files.sort(key=lambda item: item["path"].casefold())
    return {"success": True, "project": project_name, "version": version_name,
            "file_count": len(files), "truncated": len(files) >= MAX_MANIFEST_FILES,
            "returned_count": min(len(files), limit), "files": files[:limit]}


@router.get("/projects/{project_name}/compare-versions")
def compare_project_versions(
    project_name: str,
    left: Annotated[str, Query(min_length=1, max_length=40)],
    right: Annotated[str, Query(min_length=1, max_length=40)],
):
    project_path, _ = _project_or_404(project_name)
    left_path = resolve_project_path(project_name, left)
    right_path = resolve_project_path(project_name, right)
    if any(path is None or not path.is_dir() or path.parent != project_path for path in (left_path, right_path)):
        raise HTTPException(status_code=404, detail="one or both project versions not found")

    def files_in(version_path):
        output = set()
        for path in version_path.rglob("*"):
            if any(part in IGNORED_DIRS or part.startswith(".") for part in path.relative_to(version_path).parts):
                continue
            if path.is_file() and not path.is_symlink():
                resolved = path.resolve()
                if resolved.is_relative_to(version_path.resolve()):
                    output.add(path.relative_to(version_path).as_posix())
        return output

    left_files, right_files = files_in(left_path), files_in(right_path)
    common = sorted(left_files & right_files)
    changed = []
    unreadable = []
    total_bytes = 0
    max_file_bytes = 2 * 1024 * 1024
    max_total_bytes = 20 * 1024 * 1024
    for relative in common[:200]:
        left_file = (left_path / relative).resolve()
        right_file = (right_path / relative).resolve()
        if not left_file.is_relative_to(left_path.resolve()) or not right_file.is_relative_to(right_path.resolve()):
            continue
        try:
            left_size, right_size = left_file.stat().st_size, right_file.stat().st_size
            if max(left_size, right_size) > max_file_bytes or total_bytes + left_size + right_size > max_total_bytes:
                unreadable.append({"path": relative, "reason": "comparison size budget exceeded"})
                continue
            left_bytes, right_bytes = left_file.read_bytes(), right_file.read_bytes()
            total_bytes += len(left_bytes) + len(right_bytes)
            if sha256(left_bytes).digest() != sha256(right_bytes).digest():
                changed.append({"path": relative, "left_size_bytes": len(left_bytes), "right_size_bytes": len(right_bytes),
                                "left_sha256": sha256(left_bytes).hexdigest(), "right_sha256": sha256(right_bytes).hexdigest()})
        except OSError:
            unreadable.append({"path": relative, "reason": "file could not be read"})
    return {"success": True, "project": project_name, "left_version": left, "right_version": right,
            "left_file_count": len(left_files), "right_file_count": len(right_files),
            "only_in_left": sorted(left_files - right_files)[:500],
            "only_in_right": sorted(right_files - left_files)[:500],
            "common_file_count": len(left_files & right_files), "changed_common_files": changed,
            "changed_common_file_count_scanned": len(changed), "uncompared_common_files": unreadable,
            "comparison_budget": {"max_file_bytes": max_file_bytes, "max_total_bytes": max_total_bytes, "max_common_files": 200},
            "note": "Common-file content comparison uses SHA-256 within a bounded read budget. Uncompared files are listed separately."}


@router.get("/projects/{project_name}/integrity")
def project_integrity(
    project_name: str,
    version: Annotated[str | None, Query(max_length=40)] = None,
):
    project_path, project = _project_or_404(project_name)
    latest = project.get("latest") if isinstance(project.get("latest"), dict) else {}
    version_name = version or latest.get("version")
    if not isinstance(version_name, str) or not version_name:
        raise HTTPException(status_code=404, detail="project version not found")
    version_path = resolve_project_path(project_name, version_name)
    if version_path is None or not version_path.is_dir() or version_path.parent != project_path:
        raise HTTPException(status_code=404, detail="project version not found")
    findings = []
    scanned = 0
    total_bytes = 0
    oversized = []
    empty_files = []
    symlink_paths = []
    errors = []
    try:
        for path in version_path.rglob("*"):
            relative_parts = path.relative_to(version_path).parts
            if any(part in IGNORED_DIRS or part.startswith(".") for part in relative_parts):
                continue
            if path.is_symlink():
                symlink_paths.append(path.relative_to(version_path).as_posix())
                continue
            if not path.is_file():
                continue
            scanned += 1
            if scanned > MAX_MANIFEST_FILES:
                findings.append({"code": "scan_limit_reached", "severity": "info"})
                break
            try:
                resolved = path.resolve()
                if not resolved.is_relative_to(version_path.resolve()):
                    errors.append(path.relative_to(version_path).as_posix())
                    continue
                size = path.stat().st_size
                total_bytes += size
                if size == 0:
                    empty_files.append(path.relative_to(version_path).as_posix())
                if size > 10 * 1024 * 1024:
                    oversized.append({"path": path.relative_to(version_path).as_posix(), "size_bytes": size})
            except OSError:
                errors.append(path.relative_to(version_path).as_posix())
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Project integrity scan could not read the version") from exc
    if empty_files:
        findings.append({"code": "empty_files", "severity": "warning", "count": len(empty_files), "paths": empty_files[:50]})
    if oversized:
        findings.append({"code": "oversized_files", "severity": "info", "count": len(oversized), "files": oversized[:50]})
    if symlink_paths:
        findings.append({"code": "symlinks_skipped", "severity": "warning", "count": len(symlink_paths), "paths": symlink_paths[:50]})
    if errors:
        findings.append({"code": "unreadable_or_outside_paths", "severity": "warning", "count": len(errors), "paths": errors[:50]})
    if scanned == 0:
        findings.append({"code": "no_files_found", "severity": "warning"})
    return {
        "success": True, "project": project_name, "version": version_name,
        "files_scanned": min(scanned, MAX_MANIFEST_FILES), "total_bytes_scanned": total_bytes,
        "findings": findings, "finding_count": len(findings),
        "empty_files": empty_files[:50], "oversized_files": oversized[:50],
        "symlinks_skipped": symlink_paths[:50], "unreadable_or_outside_paths": errors[:50],
        "scan_truncated": scanned > MAX_MANIFEST_FILES,
        "note": "Metadata-only integrity scan. It does not execute or import generated project code.",
    }


@router.get("/projects/{project_name}/security-review")
def project_security_review(project_name: str, version: Annotated[str | None, Query(max_length=40)] = None):
    """Run a bounded heuristic scan; never execute project source."""
    project_path, project = _project_or_404(project_name)
    latest = project.get("latest") if isinstance(project.get("latest"), dict) else {}
    version_name = version or latest.get("version")
    if not isinstance(version_name, str) or not version_name:
        raise HTTPException(status_code=404, detail="project version not found")
    version_path = resolve_project_path(project_name, version_name)
    if version_path is None or not version_path.is_dir() or version_path.parent != project_path:
        raise HTTPException(status_code=404, detail="project version not found")
    source_extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".sh", ".ps1", ".json", ".yml", ".yaml"}
    rules = [
        ("dynamic_code_execution", "high", re.compile(r"\b(eval|exec)\s*\(")),
        ("shell_execution_enabled", "high", re.compile(r"\bshell\s*=\s*True\b")),
        ("unsafe_deserialization", "high", re.compile(r"\bpickle\.(loads|load)\s*\(")),
        ("disabled_tls_verification", "high", re.compile(r"(?i)(verify\s*=\s*False|rejectUnauthorized\s*:\s*False)")),
        ("process_launch", "medium", re.compile(r"\b(subprocess\.(run|Popen|call)|os\.system)\s*\(")),
        ("permissive_cors_candidate", "medium", re.compile(r"(?i)allow_origins\s*=\s*\[[^\]]*['\"]\*['\"]")),
    ]
    findings = []
    scanned_files = 0
    scanned_bytes = 0
    skipped = []
    max_files = 300
    max_file_bytes = 1048576
    max_total_bytes = 10485760
    try:
        for path in version_path.rglob("*"):
            relative = path.relative_to(version_path)
            if any(part in IGNORED_DIRS or part.startswith(".") for part in relative.parts):
                continue
            if path.is_symlink() or not path.is_file() or path.suffix.lower() not in source_extensions:
                continue
            if scanned_files >= max_files:
                skipped.append({"path": relative.as_posix(), "reason": "file limit"})
                break
            try:
                resolved = path.resolve()
                if not resolved.is_relative_to(version_path.resolve()):
                    skipped.append({"path": relative.as_posix(), "reason": "outside version root"})
                    continue
                size = path.stat().st_size
                if size > max_file_bytes or scanned_bytes + size > max_total_bytes:
                    skipped.append({"path": relative.as_posix(), "reason": "size limit"})
                    continue
                source = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                skipped.append({"path": relative.as_posix(), "reason": "read failed"})
                continue
            scanned_files += 1
            scanned_bytes += size
            for line_number, line in enumerate(source.splitlines(), start=1):
                for rule_id, severity, pattern in rules:
                    if pattern.search(line):
                        findings.append({"rule": rule_id, "severity": severity,
                                         "path": relative.as_posix(), "line": line_number})
                if len(findings) >= 500:
                    break
            if len(findings) >= 500:
                break
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Project security review could not read version") from exc
    severity_counts = Counter(item["severity"] for item in findings)
    return {
        "success": True, "project": project_name, "version": version_name,
        "scanned_files": scanned_files, "scanned_bytes": scanned_bytes,
        "finding_count": len(findings), "severity_counts": dict(severity_counts),
        "findings": findings[:500], "skipped_files": skipped[:100],
        "truncated": len(findings) >= 500 or len(skipped) > 100,
        "rules": [rule[0] for rule in rules],
        "disclaimer": "Heuristic static review only; findings may be false positives and no findings do not prove safety. Source is never executed.",
    }


@router.get("/projects/{project_name}/readiness-audit")
def project_readiness_audit(project_name: str, version: Annotated[str | None, Query(max_length=40)] = None):
    """Report 28 deterministic packaging/readiness checks without executing project code."""
    import json

    project_path, project = _project_or_404(project_name)
    latest = project.get("latest") if isinstance(project.get("latest"), dict) else {}
    version_name = version or latest.get("version")
    if not isinstance(version_name, str) or not version_name:
        raise HTTPException(status_code=404, detail="project version not found")
    version_path = resolve_project_path(project_name, version_name)
    if version_path is None or not version_path.is_dir() or version_path.parent != project_path:
        raise HTTPException(status_code=404, detail="project version not found")

    # Each check is metadata-oriented. Only small, known manifest files are read.
    root_files = {item.name.casefold(): item for item in version_path.iterdir() if not item.is_symlink()}
    def exists(*names: str) -> bool:
        return any(name.casefold() in root_files and root_files[name.casefold()].is_file() for name in names)
    def directory(*names: str) -> bool:
        return any(name.casefold() in root_files and root_files[name.casefold()].is_dir() for name in names)
    def small_text(*names: str, limit: int = 262144) -> str:
        for name in names:
            item = root_files.get(name.casefold())
            if item is None or not item.is_file() or item.is_symlink():
                continue
            try:
                if item.stat().st_size <= limit:
                    return item.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        return ""

    checks = []
    def add(check_id: str, label: str, passed: bool | None, detail: str):
        checks.append({"id": check_id, "label": label,
                       "status": "pass" if passed is True else "warning" if passed is False else "info",
                       "detail": detail[:240]})

    readme = exists("README.md", "README.rst", "README.txt", "readme")
    add("readme_present", "Project README", readme, "A README exists at the version root." if readme else "Add a README describing purpose, setup, and usage.")
    add("python_manifest", "Python dependency manifest", exists("requirements.txt", "pyproject.toml", "Pipfile", "setup.py", "setup.cfg"), "Python dependency/build metadata found." if exists("requirements.txt", "pyproject.toml", "Pipfile", "setup.py", "setup.cfg") else "No common Python dependency/build manifest found.")
    add("node_manifest", "Node package manifest", exists("package.json"), "package.json found." if exists("package.json") else "No package.json found; this is informational for non-Node projects.")
    add("python_lockfile", "Python lockfile", exists("poetry.lock", "Pipfile.lock", "uv.lock", "pdm.lock"), "A Python lockfile exists." if exists("poetry.lock", "Pipfile.lock", "uv.lock", "pdm.lock") else "No recognized Python lockfile; reproducibility may vary.")
    add("node_lockfile", "Node lockfile", exists("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock"), "A Node lockfile exists." if exists("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock") else "No recognized Node lockfile; informational when Node is not used.")
    add("tests_directory", "Tests directory", directory("tests", "test"), directory("tests", "test") and "A tests directory exists." or "No top-level tests directory found.")
    add("test_files", "Test files", None, "Test files are not executed or counted by this metadata-only audit.")
    add("license_present", "License file", exists("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"), "A license file exists." if exists("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING") else "No common license file found.")
    add("gitignore_present", "Git ignore rules", exists(".gitignore"), "A .gitignore exists." if exists(".gitignore") else "Consider adding ignore rules before sharing source.")
    add("env_example", "Environment template", exists(".env.example", ".env.sample", ".env.template"), "An environment template exists." if exists(".env.example", ".env.sample", ".env.template") else "No environment template found; document required configuration if applicable.")
    add("dockerfile_present", "Container recipe", exists("Dockerfile", "dockerfile"), "A Dockerfile exists." if exists("Dockerfile", "dockerfile") else "No Dockerfile found; optional for non-container deployments.")
    add("compose_present", "Compose configuration", exists("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"), "Compose configuration exists." if exists("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml") else "No Compose file found; optional.")
    add("ci_workflow", "CI workflow", directory(".github") and (version_path / ".github" / "workflows").is_dir(), "GitHub Actions workflow directory exists." if directory(".github") and (version_path / ".github" / "workflows").is_dir() else "No GitHub Actions workflow directory found; optional.")
    add("docs_directory", "Documentation directory", directory("docs", "documentation"), "A documentation directory exists." if directory("docs", "documentation") else "No docs directory found; README may be sufficient for small projects.")
    add("entrypoint_python", "Python entry point", exists("main.py", "app.py", "__main__.py"), "A common Python entry point exists." if exists("main.py", "app.py", "__main__.py") else "No common root Python entry point found; may be expected for libraries.")
    add("entrypoint_node", "Node entry point", exists("index.js", "index.ts", "server.js", "server.ts", "main.js", "main.ts"), "A common Node entry point exists." if exists("index.js", "index.ts", "server.js", "server.ts", "main.js", "main.ts") else "No common root Node entry point found; informational for non-Node projects.")
    add("static_assets", "Static assets directory", directory("static", "public", "assets"), "A static/public/assets directory exists." if directory("static", "public", "assets") else "No common static asset directory found; optional.")
    add("src_layout", "Source directory", directory("src", "app", "lib"), "A source directory exists." if directory("src", "app", "lib") else "No common source directory found; small projects may keep code at root.")
    add("configuration_file", "Project configuration", exists("pyproject.toml", "setup.cfg", "tox.ini", "tsconfig.json", "vite.config.ts", "webpack.config.js"), "A recognized project configuration file exists." if exists("pyproject.toml", "setup.cfg", "tox.ini", "tsconfig.json", "vite.config.ts", "webpack.config.js") else "No common project configuration file found.")
    add("editorconfig", "Editor conventions", exists(".editorconfig"), "EditorConfig exists." if exists(".editorconfig") else "Consider .editorconfig for consistent editor behavior.")
    add("security_policy", "Security policy", exists("SECURITY.md", "SECURITY.txt"), "A security policy exists." if exists("SECURITY.md", "SECURITY.txt") else "No security policy found; optional for private prototypes.")
    add("contributing_guide", "Contribution guidance", exists("CONTRIBUTING.md", "CONTRIBUTING.rst"), "Contribution guidance exists." if exists("CONTRIBUTING.md", "CONTRIBUTING.rst") else "No contribution guide found; optional for private projects.")
    add("changelog", "Change history", exists("CHANGELOG.md", "CHANGES.md", "HISTORY.md"), "A changelog exists." if exists("CHANGELOG.md", "CHANGES.md", "HISTORY.md") else "No changelog found; optional when version metadata already tracks changes.")
    add("package_json_valid", "package.json syntax", None, "package.json is absent or has not been parsed.")
    package_text = small_text("package.json")
    if package_text:
        try:
            package = json.loads(package_text)
            checks[-1] = {"id": "package_json_valid", "label": "package.json syntax",
                          "status": "pass" if isinstance(package, dict) else "warning",
                          "detail": ("package.json parses as a JSON object." if isinstance(package, dict)
                                     else "package.json must contain a JSON object.")}
            scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
            add("package_scripts", "Package scripts", isinstance(scripts, dict) and bool(scripts), "package.json declares scripts." if isinstance(scripts, dict) and scripts else "No package scripts declared.")
        except (ValueError, TypeError):
            checks[-1] = {"id": "package_json_valid", "label": "package.json syntax", "status": "warning", "detail": "package.json is not valid JSON."}
            add("package_scripts", "Package scripts", False, "Cannot inspect scripts because package.json is invalid JSON.")
    else:
        add("package_scripts", "Package scripts", None, "Not applicable unless this is a Node project.")
    requirements = small_text("requirements.txt", limit=262144)
    requirement_lines = [line.strip() for line in requirements.splitlines() if line.strip() and not line.lstrip().startswith(("#", "-"))]
    unpinned = [line for line in requirement_lines if not re.search(r"(===|==|~=|!=|<=|>=|<|>)", line)]
    add("requirements_nonempty", "Python requirements content", bool(requirement_lines) if exists("requirements.txt") else None, "requirements.txt contains dependency entries." if requirement_lines else "requirements.txt is absent or has no direct entries.")
    add("requirements_pinned", "Python dependency pinning", (not unpinned) if requirement_lines else None, "Direct requirements appear version-constrained." if requirement_lines and not unpinned else f"{len(unpinned)} direct requirement(s) lack a version constraint." if requirement_lines else "No requirements entries to assess.")
    add("secret_file_presence", "Root environment secret file", not exists(".env", ".env.local", ".env.production"), "No common root .env secret file detected." if not exists(".env", ".env.local", ".env.production") else "A root environment file exists; ensure secrets are excluded from distribution.")
    add("source_present", "Source files present", any(item.is_file() and item.suffix.lower() in {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".cs", ".cpp", ".c"} for item in root_files.values()), "A recognized source file exists at the root." if any(item.is_file() and item.suffix.lower() in {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".cs", ".cpp", ".c"} for item in root_files.values()) else "No recognized source file found at the version root.")
    add("generated_metadata", "Lumira generation metadata", exists("metadata.json"), "Lumira metadata.json exists." if exists("metadata.json") else "No metadata.json at the version root.")
    add("dependency_directory", "Vendored dependency directory", not directory("node_modules", ".venv", "venv"), "No common dependency directory is stored at the root." if not directory("node_modules", ".venv", "venv") else "Dependency files appear inside the project version; avoid bundling large local environments.")
    passed = sum(item["status"] == "pass" for item in checks)
    warnings = sum(item["status"] == "warning" for item in checks)
    info = sum(item["status"] == "info" for item in checks)
    return {
        "success": True, "project": project_name, "version": version_name,
        "check_count": len(checks), "passed": passed, "warnings": warnings, "informational": info,
        "readiness_score": round(passed * 100 / len(checks)) if checks else 0,
        "checks": checks, "note": "Static packaging/readiness guidance only. It does not execute code, install dependencies, or prove runtime correctness."
    }
