from __future__ import annotations

import ast
from datetime import UTC, datetime
import re
from typing import Any

from app.services.autonomous_development.worker.development_worker import DevelopmentWorker
from app.services.autonomous_development.development_backlog_service import DevelopmentBacklogService
from app.services.workflow_recovery.run_recovery_service import RunRecoveryService
from app.services.work_items.work_item_service import WorkItemService


class DevelopmentAuditService:
    """Collect bounded repository evidence and recoverable development runs."""

    MAX_RECOVERY_CANDIDATES = 5
    MAX_INTEGRATION_FINDINGS = 12
    DOMAIN_PREFIXES = {
        "backend": ("app/",),
        "core": ("app/core/", "core/"),
        "agents": ("app/agents/",),
        "services": ("app/services/",),
        "routes": ("app/routes/",),
        "tests": ("tests/",),
        "desktop": ("lumira_desktop/src/",),
        "memory": ("app/services/memory/", "memory/", "data/"),
        "sessions": ("app/services/sessions/",),
        "goals": ("app/services/goals/",),
        "projects": ("app/services/projects/", "app/services/project_context/"),
        "workflows": ("app/agents/workflow_engine.py", "app/services/work_items/", "app/routes/workflows.py"),
        "recovery": ("app/services/workflow_recovery/",),
        "artifacts": ("app/services/artifacts/", "app/routes/artifacts.py"),
        "voice": ("app/services/voice/", "app/routes/voice_capture.py"),
        "search": ("app/services/search/", "app/routes/search.py"),
        "providers": ("app/services/providers/", "app/services/autonomous_development/worker/"),
        "modes": ("app/services/modes/",),
        "devices": ("app/services/devices/", "app/routes/devices.py"),
        "authentication": ("app/services/auth/", "app/routes/auth.py"),
        "persistence": ("app/services/persistence/",),
    }

    def __init__(
        self,
        worker: DevelopmentWorker,
        *,
        work_items: WorkItemService | None = None,
        recovery: RunRecoveryService | None = None,
        backlog: DevelopmentBacklogService | None = None,
    ) -> None:
        self.worker = worker
        self.work_items = work_items or WorkItemService()
        self.recovery = recovery or RunRecoveryService()
        self.backlog = backlog

    def _behavioral_gate(self) -> dict[str, Any]:
        """Refuse to launch project-controlled tests/build scripts without OS isolation."""
        commands = [
            ["python", "-m", "pytest", "-q"],
            ["npm.cmd", "test", "--", "--run"],
            ["npm.cmd", "run", "build"],
            ["npm.cmd", "run", "lint"],
        ]
        return {
            "status": "blocked",
            "reason": (
                "OS-level sandboxing is not implemented. Audit will not execute "
                "project-controlled pytest/npm commands without verified isolation."
            ),
            "commands": [
                {"command": command, "status": "not_run", "passed": False}
                for command in commands
            ],
            "expected_command_count": len(commands),
        }

    def run(self) -> dict[str, Any]:
        inspection = self.worker.inspect()
        findings = list(inspection.get("audit_findings", []))
        checks: dict[str, Any] = {}
        findings.extend(self._domain_inventory(inspection["files"], checks))
        findings.extend(self._router_registration_findings(inspection["files"], checks))
        findings.extend(self._desktop_api_contract_findings(inspection["files"], checks))
        findings.extend(self._desktop_capability_findings(inspection["files"], checks))
        findings.extend(self._security_findings(inspection["files"], checks))
        findings.extend(self._source_integrity_findings(inspection["files"], checks))
        findings = self._deduplicate_findings(findings)[: self.MAX_INTEGRATION_FINDINGS]
        behavioral_gate = self._behavioral_gate()
        checks["behavioral_gate"] = behavioral_gate
        gate_passed = behavioral_gate["status"] == "passed"
        terminal_security = self._project_terminal_security_status(inspection["files"])
        checks["project_terminal_security"] = terminal_security

        existing_keys = {(item.get("path"), item.get("objective")) for item in findings if isinstance(item, dict)}
        historical_recovery: list[dict[str, Any]] = []

        runs_by_workflow = {}
        completed_objectives = set()
        if self.backlog is not None:
            latest_program = self.backlog.latest_program()
            if latest_program is not None:
                completed_objectives = {
                    task["objective"].casefold()
                    for task in latest_program["tasks"]
                    if task.get("status") == "completed"
                }
        for run in self.recovery.list_runs(limit=100):
            if not isinstance(run, dict):
                continue
            plan = run.get("plan", {})
            if isinstance(plan, dict) and plan.get("autonomous_development"):
                runs_by_workflow[plan.get("workflow_id")] = run

        for workflow in self.work_items.list_workflows(category="operations", limit=200):
            if workflow.get("title") not in {
                "Autonomous Lumira Development",
                "Bounded Lumira completion workflow",
            }:
                continue
            if workflow.get("status") not in {"failed", "blocked", "in_progress"}:
                continue
            run = runs_by_workflow.get(workflow.get("workflow_id"))
            if (
                not run
                or not run.get("resume_allowed")
                or run.get("resume_count", 0) >= self.recovery.MAX_RESUMES
                or not run.get("safe_resume_point")
            ):
                continue
            last_error = str(run.get("error") or "")
            provider_retry_exhausted = (
                "provider_retry_exhausted" in last_error
                or "Provider did not produce applicable changes after 2 bounded attempts." in last_error
            )
            objective = workflow.get("request", "").strip()
            if gate_passed and provider_retry_exhausted:
                historical_recovery.append({
                    "workflow_id": workflow.get("workflow_id"),
                    "recovery_run_id": run.get("run_id"),
                    "objective": objective,
                    "reason": "Historical provider failure is superseded by the passing whole-system behavioral gate.",
                })
                continue
            if provider_retry_exhausted and not gate_passed:
                if not terminal_security["os_sandbox"] and "sandbox" in objective.casefold():
                    reason = (
                        "Blocked by the missing verified OS sandbox. Preserve this as a "
                        "completion blocker instead of retrying provider-generated changes."
                    )
                else:
                    reason = (
                        "Provider attempts were exhausted while the behavioral/build/lint "
                        "gate remains unavailable. Preserve the checkpoint instead of "
                        "re-queuing work that cannot yet be verified."
                    )
                historical_recovery.append({
                    "workflow_id": workflow.get("workflow_id"),
                    "recovery_run_id": run.get("run_id"),
                    "objective": objective,
                    "reason": reason,
                })
                continue
            task = next(
                (item for item in workflow.get("tasks", []) if item.get("status") in {"failed", "in_progress", "blocked"}),
                None,
            )
            key = ("recovery", objective)
            if not objective or key in existing_keys or objective.casefold() in completed_objectives:
                continue
            findings.append({
                "path": "recovery:" + str(run["run_id"]),
                "objective": objective,
                "acceptance": "Resume from the persisted safe checkpoint, validate the applied state, and complete or persist a specific blocker.",
                "evidence": {
                    "workflow_id": workflow["workflow_id"],
                    "recovery_run_id": run["run_id"],
                    "workflow_status": workflow["status"],
                    "failed_task": task.get("title") if task else None,
                    "failed_stage": run.get("current_stage"),
                    "safe_resume_point": run.get("safe_resume_point"),
                    "last_error": run.get("error"),
                },
                "recovery_run_id": run["run_id"],
                "workflow_id": workflow["workflow_id"],
                "category": "recovery",
                "priority": 90,
            })
            existing_keys.add(key)
            if len(findings) >= self.worker.MAX_AUDIT_FINDINGS + self.MAX_RECOVERY_CANDIDATES:
                break

        checks["historical_recovery"] = {
            "status": (
                "superseded"
                if gate_passed and historical_recovery
                else "blocked"
                if historical_recovery
                else "none"
            ),
            "count": len(historical_recovery),
            "runs": historical_recovery,
        }
        findings = self._deduplicate_findings(findings)[: self.MAX_INTEGRATION_FINDINGS + self.MAX_RECOVERY_CANDIDATES]
        blockers: list[str] = []
        if findings:
            blockers.append("One or more current repository integration findings remain unresolved.")
        if not gate_passed:
            blockers.append("The final behavioral/build/lint gate did not pass all required commands.")
        if not terminal_security["os_sandbox"]:
            blockers.append(
                "Project terminal commands are allowlisted but are not isolated by an OS sandbox."
            )
        whole_lumira = not findings and gate_passed and terminal_security["os_sandbox"]

        return {
            "workspace": ".",
            "file_count": inspection["file_count"],
            "findings": findings,
            "checks": checks,
            "coverage": {
                "whole_lumira": whole_lumira,
                "domains": sorted(self.DOMAIN_PREFIXES),
                "source_file_count": inspection["file_count"],
            },
            "audited_at": datetime.now(UTC).isoformat(),
            "completion_ready": whole_lumira,
            "completion_blockers": blockers,
            "limits": {
                "max_source_files": self.worker.MAX_AUDIT_FILES,
                "max_source_chars": self.worker.MAX_AUDIT_SOURCE_CHARS,
                "max_findings": self.worker.MAX_AUDIT_FINDINGS + self.MAX_RECOVERY_CANDIDATES,
            },
        }

    def _project_terminal_security_status(self, files: list[str]) -> dict[str, Any]:
        """Report terminal isolation conservatively; allowlisting is not sandboxing."""
        terminal_path = "app/services/workspace/project_terminal_service.py"
        normalized = {path.replace("\\", "/") for path in files}
        source = ""
        if terminal_path in normalized:
            try:
                source = self.worker.read_file(terminal_path)
            except (OSError, UnicodeDecodeError):
                source = ""
        # A Boolean declaration is not evidence of an OS security boundary.
        # Fail closed until a concrete sandbox provider and verifier are implemented.
        return {
            # Finding the service source is not completion of its security gate.
            # Keep the status blocked until an OS sandbox is implemented and verified.
            "status": "blocked" if source else "unavailable",
            "shell": False,
            "command_allowlist": bool(source and "COMMANDS:" in source),
            "os_sandbox": False,
            "sandbox_verification": "not_implemented",
            "untrusted_project_code_execution_possible": True,
        }

    @staticmethod
    def _deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique = []
        seen = set()
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            key = (finding.get("path"), finding.get("objective"))
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        return unique

    def _domain_inventory(
        self,
        files: list[str],
        checks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        findings = []
        normalized = [path.replace("\\", "/") for path in files]
        counts = {
            domain: sum(any(path.startswith(prefix) for prefix in prefixes) for path in normalized)
            for domain, prefixes in self.DOMAIN_PREFIXES.items()
        }
        checks["domain_inventory"] = counts
        for domain, count in counts.items():
            if count == 0:
                findings.append({
                    "path": domain,
                    "category": "missing_subsystem",
                    "priority": 70,
                    "objective": f"Audit missing {domain} subsystem source",
                    "acceptance": f"Establish whether the missing {domain} source area is intentionally absent or represents unfinished functionality.",
                    "evidence": {"source_file_count": 0, "expected_area": domain},
                })
        return findings

    def _router_registration_findings(
        self,
        files: list[str],
        checks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        main_path = "app/main.py"
        normalized = {path.replace("\\", "/") for path in files}
        if main_path not in normalized:
            checks["router_registration"] = {"status": "unavailable", "reason": "app/main.py missing"}
            return [{
                "path": main_path,
                "category": "api_registration",
                "priority": 100,
                "objective": "Restore the backend application/router entry point",
                "acceptance": "The FastAPI app imports and registers the route modules.",
                "evidence": "app/main.py is absent from workspace inspection.",
            }]

        try:
            main_source = self.worker.read_file(main_path)
        except (OSError, UnicodeDecodeError):
            checks["router_registration"] = {"status": "unavailable", "reason": "app/main.py unreadable"}
            return []

        findings = []
        router_modules = []
        for path in normalized:
            if not path.startswith("app/routes/") or not path.endswith(".py") or path.endswith("/__init__.py"):
                continue
            try:
                source = self.worker.read_file(path)
            except (OSError, UnicodeDecodeError):
                continue
            if not re.search(r"\brouter\s*=\s*APIRouter\s*\(", source):
                continue
            module = path.removeprefix("app/routes/").removesuffix(".py")
            import_pattern = re.compile(
                rf"from\s+app\.routes\.{re.escape(module)}\s+import\s*(?:\(\s*)?router(?:\s+as\s+(\w+))?",
                re.MULTILINE,
            )
            match = import_pattern.search(main_source)
            alias = match.group(1) if match else None
            imported = match is not None
            registered = bool(alias and re.search(rf"include_router\s*\(\s*{re.escape(alias)}\b", main_source, re.MULTILINE))
            if imported and not alias:
                registered = bool(re.search(r"include_router\s*\(\s*router\b", main_source, re.MULTILINE))
            router_modules.append({"module": module, "imported": imported, "registered": registered})
            if not imported or not registered:
                findings.append({
                    "path": path,
                    "category": "disconnected_route",
                    "priority": 90,
                    "objective": f"Register the {module} API router in app.main",
                    "acceptance": "The route module is imported and included by the FastAPI application, and an API test exercises its route.",
                    "evidence": {"imported": imported, "registered": registered, "router_assignment": "router = APIRouter(...)"},
                })
        checks["router_registration"] = {
            "status": "completed",
            "router_count": len(router_modules),
            "registered_count": sum(item["registered"] for item in router_modules),
            "modules": router_modules,
        }
        return findings

    def _desktop_api_contract_findings(
        self,
        files: list[str],
        checks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        client_path = "lumira_desktop/src/api/client.ts"
        normalized_files = {path.replace("\\", "/") for path in files}
        if client_path not in normalized_files:
            checks["desktop_api_contract"] = {"status": "unavailable", "reason": "desktop API client missing"}
            return []
        try:
            source = self.worker.read_file(client_path)
            from app.main import app

            registered_paths = {
                self._normalize_route_path(path)
                for path in app.openapi().get("paths", {})
            }
        except Exception as exc:
            checks["desktop_api_contract"] = {"status": "failed", "error_type": type(exc).__name__}
            return []

        requests = []
        for match in re.finditer(r"request(?:<[^>]+>)?\(\s*([`\"])([^`\"]+)\1", source):
            raw_path = match.group(2).split("?", 1)[0]
            raw_path = raw_path.split("${", 1)[0] if "${" in raw_path and "}" not in raw_path.split("${", 1)[-1] else raw_path
            route = self._normalize_route_path(re.sub(r"\$\{[^}]+\}", "{}", raw_path))
            if not route or route == "/":
                continue
            requests.append(route)

        unmatched = []
        for route in sorted(set(requests)):
            covered = route in registered_paths
            if not covered and route not in {"/openapi.json"}:
                unmatched.append(route)
        checks["desktop_api_contract"] = {
            "status": "completed",
            "frontend_path_count": len(set(requests)),
            "backend_path_count": len(registered_paths),
            "unmatched_paths": unmatched,
        }
        return [{
            "path": client_path,
            "category": "frontend_backend_contract",
            "priority": 95,
            "objective": f"Map desktop API path {path} to a real backend route",
            "acceptance": "The desktop API call uses a registered backend route and a contract test covers its request/response.",
            "evidence": {"frontend_path": path, "backend_path_count": len(registered_paths)},
        } for path in unmatched]

    def _desktop_capability_findings(
        self,
        files: list[str],
        checks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        panel_path = "lumira_desktop/src/components/RightPanel/RightPanel.tsx"
        paths = {path.replace("\\", "/") for path in files}
        if panel_path not in paths:
            checks["desktop_capabilities"] = {"status": "unavailable"}
            return []
        try:
            source = self.worker.read_file(panel_path)
        except (OSError, UnicodeDecodeError):
            checks["desktop_capabilities"] = {"status": "unavailable"}
            return []
        findings = []
        explicit_gaps = (
            ("Terminal unavailable", "Implement a sandboxed project terminal provider using only the validation command allowlist."),
            ("Preview unavailable", "Implement safe project preview registration and lifecycle for generated project versions."),
        )
        for marker, objective in explicit_gaps:
            if marker in source:
                findings.append({
                    "path": panel_path,
                    "category": "desktop_capability_gap",
                    "priority": 65,
                    "objective": objective,
                    "acceptance": "The desktop capability is backed by a real backend contract, persists state where required, and does not enable arbitrary shell execution.",
                    "evidence": {"visible_state": marker, "source": panel_path},
                })
        terminal_ui_present = "Terminal unavailable" not in source
        terminal_security = self._project_terminal_security_status(files)
        checks["desktop_capabilities"] = {
            "status": "completed",
            "terminal_ui_present": terminal_ui_present,
            # A visible UI or registered route is not evidence that execution is safe.
            "terminal_available": terminal_ui_present and terminal_security.get("os_sandbox") is True,
            "preview_provider_registered": "Preview unavailable" not in source,
        }
        return findings

    def _security_findings(
        self,
        files: list[str],
        checks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        findings = []
        checked = 0
        unsafe = []
        for path in files:
            normalized = path.replace("\\", "/")
            if not normalized.startswith(("app/", "core/", "lumira_desktop/src/")) or not normalized.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                continue
            if normalized.lower().endswith((".backup", ".bak")):
                continue
            checked += 1
            try:
                source = self.worker.read_file(path)
            except (OSError, UnicodeDecodeError):
                continue
            if not normalized.endswith(".py"):
                continue
            try:
                tree = ast.parse(source.removeprefix("\ufeff"), filename=path)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                call_name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                if call_name in {"system", "popen"}:
                    unsafe.append({"path": path, "line": getattr(node, "lineno", None), "pattern": f"{call_name}()"})
                    continue
                if call_name in {"run", "Popen", "call", "check_call", "check_output"} and any(
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                    for keyword in node.keywords
                ):
                    unsafe.append({"path": path, "line": getattr(node, "lineno", None), "pattern": "shell=True process call"})
        for evidence in unsafe[: self.MAX_INTEGRATION_FINDINGS]:
            path = evidence["path"]
            findings.append({
                "path": path,
                "category": "unsafe_process_execution",
                "priority": 100,
                "objective": f"Remove or explicitly sandbox unsafe process execution in {path}",
                "acceptance": "Validation uses shell=False and only the closed allowlisted commands; tests prove arbitrary commands are rejected.",
                "evidence": evidence,
            })
        checks["security_shell_scan"] = {
            "status": "completed",
            "source_files_checked": checked,
            "unsafe_process_calls": unsafe,
        }
        return findings

    def _source_integrity_findings(
        self,
        files: list[str],
        checks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        normalized = {
            path.replace("\\", "/")
            for path in files
            if path.replace("\\", "/").endswith(".py")
            and not path.lower().endswith((".backup", ".bak"))
        }
        candidates = [
            path for path in normalized
            if path.startswith(("app/", "core/"))
        ][: self.worker.MAX_AUDIT_FILES]
        module_names = set()
        for path in normalized:
            if path.endswith("/__init__.py"):
                module_names.add(path[: -len("/__init__.py")].replace("/", "."))
            elif path.endswith(".py"):
                module_names.add(path[:-3].replace("/", "."))

        def module_exists(module: str) -> bool:
            if not module:
                return True
            if module in module_names:
                return True
            prefix = module.replace(".", "/") + "/"
            return any(path.startswith(prefix) for path in normalized)

        findings = []
        syntax_errors = []
        unresolved_imports = []
        chars = 0
        for path in candidates:
            if chars >= self.worker.MAX_AUDIT_SOURCE_CHARS:
                break
            try:
                source = self.worker.read_file(path)
            except (OSError, UnicodeDecodeError):
                continue
            if len(source) > self.worker.MAX_FILE_SIZE:
                continue
            if chars + len(source) > self.worker.MAX_AUDIT_SOURCE_CHARS:
                break
            chars += len(source)
            try:
                tree = ast.parse(source.removeprefix("\ufeff"), filename=path)
            except SyntaxError as exc:
                syntax_errors.append({"path": path, "line": exc.lineno, "message": str(exc.msg)[:300]})
                continue
            package = path[:-3].split("/")[:-1]
            if path.endswith("/__init__.py"):
                package = path[: -len("/__init__.py")].split("/")
            for node in ast.walk(tree):
                imported = []
                if isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if node.level:
                        base = package[: max(0, len(package) - node.level + 1)]
                        module = ".".join(base + ([module] if module else []))
                    imported.append(module)
                for module in imported:
                    if module == "app" or module.startswith("app.") or module == "core" or module.startswith("core."):
                        if not module_exists(module):
                            unresolved_imports.append({"path": path, "line": getattr(node, "lineno", None), "module": module})

        for item in syntax_errors[: self.MAX_INTEGRATION_FINDINGS]:
            findings.append({
                "path": item["path"],
                "category": "syntax_error",
                "priority": 100,
                "objective": f"Fix Python syntax error in {item['path']}",
                "acceptance": "The module parses/compiles and its focused tests pass.",
                "evidence": item,
            })
        for item in unresolved_imports[: self.MAX_INTEGRATION_FINDINGS - len(findings)]:
            findings.append({
                "path": item["path"],
                "category": "broken_local_import",
                "priority": 95,
                "objective": f"Resolve missing local module import {item['module']} in {item['path']}",
                "acceptance": "The local module import resolves in the project environment and focused tests pass.",
                "evidence": item,
            })
        checks["source_integrity"] = {
            "status": "completed",
            "python_files_checked": len(candidates),
            "source_chars_checked": chars,
            "syntax_error_count": len(syntax_errors),
            "unresolved_local_import_count": len(unresolved_imports),
        }
        return findings

    @staticmethod
    def _normalize_route_path(path: str) -> str:
        normalized = re.sub(r"\{[^{}]+\}", "{}", path)
        if len(normalized) > 1:
            normalized = normalized.rstrip("/")
        return normalized