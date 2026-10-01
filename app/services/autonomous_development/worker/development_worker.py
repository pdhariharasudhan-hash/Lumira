from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .development_code_generator import DevelopmentCodeGenerator
from .workspace_boundary import WorkspaceBoundary


@dataclass
class DevelopmentIteration:
    number: int
    status: str = "created"
    files_changed: list[str] = field(default_factory=list)
    command: list[str] = field(default_factory=list)
    output: str = ""
    return_code: int | None = None


class DevelopmentWorker:
    """
    Bounded workspace worker for autonomous development.

    Mechanical flow:

        inspect
        ↓
        generate changes
        ↓
        verify proposed old content
        ↓
        apply changes
        ↓
        validate

    Reasoning and planning remain outside this class.
    """

    MAX_ITERATIONS = 5
    MAX_FILES_PER_ITERATION = 20
    MAX_FILE_SIZE = 500_000
    MAX_OUTPUT_CHARS = 50_000
    DEFAULT_TIMEOUT = 120
    MAX_PROVIDER_ATTEMPTS = 2
    MAX_AUDIT_FILES = 400
    MAX_AUDIT_SOURCE_CHARS = 1_000_000
    MAX_AUDIT_FINDINGS = 5

    ALLOWED_COMMANDS = {
        ("python", "-m", "pytest"),
        ("python", "-m", "pytest", "-q"),
        ("python", "-m", "compileall"),
        ("python", "-m", "compileall", "app"),
        ("npm", "test"),
        ("npm", "test", "--", "--run"),
        ("npm", "run", "build"),
    }

    def __init__(
        self,
        workspace: str | Path,
        *,
        max_iterations: int = MAX_ITERATIONS,
        timeout_seconds: int = DEFAULT_TIMEOUT,
        code_generator: DevelopmentCodeGenerator | None = None,
    ) -> None:
        self.boundary = WorkspaceBoundary(workspace)

        self.max_iterations = max(
            1,
            min(
                max_iterations,
                self.MAX_ITERATIONS,
            ),
        )

        self.timeout_seconds = max(
            10,
            min(
                timeout_seconds,
                600,
            ),
        )

        self.code_generator = (
            code_generator
            or DevelopmentCodeGenerator(
                self.boundary.workspace
            )
        )

        self.iterations: list[DevelopmentIteration] = []

    def inspect(self) -> dict[str, Any]:
        files = self.boundary.list_files()

        return {
            "workspace": str(
                self.boundary.workspace
            ),
            "file_count": len(files),
            "files": files,
            "audit_findings": self._audit_workspace(files),
        }

    def _audit_workspace(
        self,
        files: list[str],
    ) -> list[dict[str, Any]]:
        source_files = [
            relative
            for relative in files
            if relative.endswith((".py", ".ts", ".tsx", ".js", ".jsx"))
            and relative.startswith(
                (
                    "app/",
                    "app\\",
                    "core/",
                    "core\\",
                    "lumira_desktop/src/",
                    "lumira_desktop\\src\\",
                )
            )
            and not relative.lower().endswith((".backup", ".bak"))
        ]
        source_files.sort(
            key=lambda path: (
                0 if path.replace("\\", "/").startswith("app/agents/") else 1,
                path.casefold(),
            )
        )
        findings: list[dict[str, Any]] = []
        chars_read = 0

        research_agent = "app/agents/research_agent.py"
        research_service = "app/services/research/research_capability_service.py"
        if research_agent in files and research_service in files:
            try:
                agent_source = self.read_file(research_agent)
            except (OSError, UnicodeDecodeError):
                agent_source = ""
            chars_read += len(agent_source)
            if (
                '"provider_unavailable"' in agent_source
                and "ResearchCapabilityService" not in agent_source
            ):
                findings.append(
                    {
                        "path": research_agent,
                        "objective": "Connect research dispatch to the existing ResearchCapabilityService",
                        "acceptance": "ResearchAgent uses the existing capability service and reports configured-provider or local-retrieval results accurately.",
                        "evidence": "ResearchAgent returns provider_unavailable directly while ResearchCapabilityService exists.",
                    }
                )

        for relative_path in source_files[: self.MAX_AUDIT_FILES]:
            if len(findings) >= self.MAX_AUDIT_FINDINGS or chars_read >= self.MAX_AUDIT_SOURCE_CHARS:
                break
            if relative_path == research_agent:
                continue
            try:
                content = self.read_file(relative_path)
            except (OSError, UnicodeDecodeError):
                continue
            remaining = self.MAX_AUDIT_SOURCE_CHARS - chars_read
            content = content[: min(20_000, remaining)]
            chars_read += len(content)
            for line_number, line in enumerate(content.splitlines(), start=1):
                stripped = line.lstrip()
                comment_start = min(
                    (
                        position
                        for position in (
                            stripped.find("#"),
                            stripped.find("//"),
                            stripped.find("/*"),
                            stripped.find("*"),
                        )
                        if position >= 0
                    ),
                    default=-1,
                )
                comment = stripped[comment_start:] if comment_start >= 0 else ""
                marker = next(
                    (
                        token
                        for token in ("TODO", "FIXME")
                        if token in comment.upper()
                    ),
                    None,
                )
                if marker is None:
                    continue
                findings.append(
                    {
                        "path": relative_path,
                        "objective": (
                            f"Audit and resolve the {marker} marker at "
                            f"{relative_path}:{line_number}"
                        ),
                        "acceptance": (
                            "Determine from surrounding code whether the marker is unfinished, "
                            "intentionally deferred, obsolete, or already implemented; fix only "
                            "a verified unfinished behavior and add a focused test."
                        ),
                        "evidence": line.strip()[:500],
                    }
                )
                if len(findings) >= self.MAX_AUDIT_FINDINGS:
                    break

        return findings

    def read_file(
        self,
        relative_path: str,
    ) -> str:
        return self.boundary.read_text(
            relative_path
        )

    def write_file(
        self,
        relative_path: str,
        content: str,
        *,
        iteration: int,
    ) -> str:
        if (
            iteration < 1
            or iteration > self.max_iterations
        ):
            raise ValueError(
                "Invalid development iteration."
            )

        if len(content) > self.MAX_FILE_SIZE:
            raise ValueError(
                "File exceeds maximum size of "
                f"{self.MAX_FILE_SIZE} bytes."
            )

        path = self.boundary.write_text(
            relative_path,
            content,
        )

        record = self._get_iteration(
            iteration
        )

        relative = str(
            path.relative_to(
                self.boundary.workspace
            )
        )

        if relative not in record.files_changed:
            if (
                len(record.files_changed)
                >= self.MAX_FILES_PER_ITERATION
            ):
                raise ValueError(
                    "Maximum changed files per "
                    "iteration reached."
                )

            record.files_changed.append(
                relative
            )

        return relative

    def generate_changes(
        self,
        *,
        goal: str,
        iteration: int,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ask the configured development provider for
        structured source-file changes.

        No files are modified by this method.
        """

        self.begin_iteration(
            iteration
        )

        inspection = self.inspect()

        # Keep local development models usable by bounding the amount of
        # repository context sent to the provider.  The change limit above
        # controls writes; these limits control model input size.
        MAX_PROVIDER_FILES = 12
        MAX_PROVIDER_CONTEXT_CHARS = 100_000
        MAX_PROVIDER_FILE_CHARS = 50_000

        excluded_parts = {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "generated",
            "dist",
            "build",
            "coverage",
            ".next",
            ".cache",
            "autodev_review",
            ".pytest-work",
        }

        def is_candidate(relative_path: str) -> bool:
            parts = Path(relative_path).parts
            path = Path(relative_path)
            return not path.name.lower().endswith(
                (".backup", ".backup-context", ".bak", ".zip")
            ) and not any(
                part in excluded_parts
                for part in parts
            )

        request_context = context or {}

        relevance_text = " ".join(
            [
                goal,
                str(request_context.get("plan", "")),
                str(request_context.get("task", "")),
                str(request_context.get("acceptance_criteria", "")),
                str(request_context.get("diagnosis", "")),
                str(request_context.get("previous_validation", "")),
            ]
        ).lower()

        keywords = {
            token.strip(".,:;()[]{}<>/\\")
            for token in relevance_text.split()
            if len(token.strip(".,:;()[]{}<>/\\") or "") >= 3
        }

        candidates = []

        for relative_path in inspection["files"]:
            if not is_candidate(relative_path):
                continue

            path_text = relative_path.lower()
            path_tokens = set(
                token.strip(".,:;()[]{}<>/\\")
                for part in Path(relative_path).parts
                for token in Path(part).stem.lower().replace("_", " ").replace("-", " ").split()
                if len(token) >= 3
            )

            score = len(keywords.intersection(path_tokens))
            requested_paths = request_context.get("relevant_files", [])
            if isinstance(requested_paths, list) and any(
                isinstance(requested, str)
                and requested.replace("\\", "/").casefold()
                == relative_path.replace("\\", "/").casefold()
                for requested in requested_paths
            ):
                score += 20

            if (
                keywords.intersection({"test", "tests", "pytest"})
                and (path_text.startswith("tests\\") or path_text.startswith("tests/"))
            ):
                score += 4

            # Prefer the application and test source tree over miscellaneous
            # repository metadata.
            if path_text.startswith("app" + str(Path("/"))):
                score += 1
            if path_text.startswith("app\\") or path_text.startswith("app/"):
                score += 3
            if path_text.startswith("tests\\") or path_text.startswith("tests/"):
                score += 2
            if path_text.endswith(".py"):
                score += 1
            if path_text.endswith((".ts", ".tsx")):
                score += 1

            if (
                keywords.intersection({"test", "tests", "pytest"})
                and (path_text.startswith("tests\\") or path_text.startswith("tests/"))
            ):
                try:
                    source_size = self.boundary.resolve(relative_path).stat().st_size
                except OSError:
                    source_size = 0
                if source_size > 35_000:
                    score -= 8
                elif source_size > 20_000:
                    score -= 4

            candidates.append((score, relative_path))

        candidates.sort(
            key=lambda item: (-item[0], item[1].lower())
        )

        if candidates and candidates[0][0] > 0:
            relevance_floor = candidates[0][0] - 1
            candidates = [
                item
                for item in candidates
                if item[0] >= relevance_floor
            ]
        else:
            candidates = candidates[:3]

        files = []
        total_chars = 0

        for _, relative_path in candidates:
            if len(files) >= MAX_PROVIDER_FILES:
                break

            try:
                content = self.read_file(
                    relative_path
                )
            except (
                OSError,
                UnicodeDecodeError,
            ):
                continue

            if not content:
                continue

            if len(content) > MAX_PROVIDER_FILE_CHARS:
                content = content[
                    :MAX_PROVIDER_FILE_CHARS
                ]

            remaining = (
                MAX_PROVIDER_CONTEXT_CHARS
                - total_chars
            )

            if remaining <= 0:
                break

            if len(content) > remaining:
                content = content[:remaining]

            files.append(
                {
                    "path": relative_path,
                    "content": content,
                }
            )

            total_chars += len(content)

            if total_chars >= MAX_PROVIDER_CONTEXT_CHARS:
                break

        base_context = {
            **request_context,
            "task": request_context.get("task", goal),
            "acceptance_criteria": request_context.get(
                "acceptance_criteria",
                [goal],
            ),
            "relevant_files": [item["path"] for item in files],
            "iteration": iteration,
            "provider_attempt": 1,
            "workspace": inspection["workspace"],
            "provider_context": {
                "max_files": MAX_PROVIDER_FILES,
                "max_total_chars": MAX_PROVIDER_CONTEXT_CHARS,
                "max_file_chars": MAX_PROVIDER_FILE_CHARS,
                "files_selected": len(files),
                "total_chars": total_chars,
            },
        }

        last_result: dict[str, Any] = {
            "success": False,
            "code": "provider_no_change",
            "message": "Provider did not return changes.",
        }

        for attempt in range(1, self.MAX_PROVIDER_ATTEMPTS + 1):
            generation_context = {
                **base_context,
                "provider_attempt": attempt,
            }
            if attempt > 1:
                generation_context["previous_provider_result"] = {
                    "code": last_result.get("code"),
                    "message": last_result.get("message"),
                }
                generation_context["retry_instruction"] = (
                    "The requested acceptance criteria are not yet met. "
                    "Use the relevant supplied files and return a minimal "
                    "structured change, or explicitly explain why the goal "
                    "is already satisfied."
                )

            last_result = self.code_generator.generate_changes(
                goal=goal,
                files=files,
                context=generation_context,
            )

            if not isinstance(last_result, dict):
                last_result = {
                    "success": False,
                    "code": "provider_invalid_response",
                    "message": "Provider returned an invalid result object.",
                }
                continue

            if last_result.get("success") and isinstance(
                last_result.get("changes"), list
            ):
                try:
                    from .change_applier import ChangeApplier

                    changes = [
                        ChangeApplier.from_dict(value)
                        for value in last_result["changes"]
                    ]
                    ChangeApplier(self.boundary).validate(changes)
                except Exception as exc:
                    last_result = {
                        "success": False,
                        "code": "provider_invalid_changes",
                        "message": str(exc)[:1000],
                    }
                    continue
                return last_result

            if last_result.get("code") not in {
                "provider_no_change",
                "provider_invalid_changes",
                "invalid_provider_changes",
                "no_changes_generated",
            }:
                return last_result

        if (
            last_result.get("code") == "provider_no_change"
            and last_result.get("already_satisfied") is True
            and isinstance(last_result.get("evidence"), str)
            and last_result["evidence"].strip()
        ):
            return {
                "success": True,
                "status": "no_change",
                "already_satisfied": True,
                "evidence": last_result["evidence"][:1000],
                "changes": [],
            }

        return {
            **last_result,
            "success": False,
            "code": "provider_retry_exhausted",
            "attempts": self.MAX_PROVIDER_ATTEMPTS,
            "last_error": {
                "code": last_result.get("code"),
                "message": str(last_result.get("message", ""))[:1000],
                "status": last_result.get("status"),
            },
            "message": (
                "Provider did not produce applicable changes after "
                f"{self.MAX_PROVIDER_ATTEMPTS} bounded attempts."
            ),
        }

    def apply_changes(
        self,
        *,
        iteration: int,
        changes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Safely apply provider-generated changes.

        Existing files require old_content to match the
        current workspace exactly. This prevents a stale
        provider response from overwriting newer work.
        """

        record = self._get_iteration(
            iteration
        )

        if len(changes) > self.MAX_FILES_PER_ITERATION:
            return {
                "success": False,
                "code": "too_many_changes",
                "message": (
                    "Provider returned more changes than "
                    "the iteration limit allows."
                ),
            }

        applied: list[str] = []

        try:
            for change in changes:
                if not isinstance(
                    change,
                    dict,
                ):
                    raise ValueError(
                        "Each change must be an object."
                    )

                relative_path = change.get(
                    "path"
                )

                if not isinstance(
                    relative_path,
                    str,
                ) or not relative_path.strip():
                    raise ValueError(
                        "Change path is required."
                    )

                new_content = change.get(
                    "new_content"
                )

                if not isinstance(
                    new_content,
                    str,
                ):
                    raise ValueError(
                        f"new_content is required for "
                        f"{relative_path}."
                    )

                if len(new_content) > self.MAX_FILE_SIZE:
                    raise ValueError(
                        f"File exceeds maximum size: "
                        f"{relative_path}"
                    )

                current_exists = self.boundary.exists(
                    relative_path
                )

                if current_exists:
                    current_content = self.read_file(
                        relative_path
                    )
                else:
                    current_content = ""

                old_content = change.get(
                    "old_content"
                )

                if current_exists:
                    if not isinstance(
                        old_content,
                        str,
                    ):
                        raise ValueError(
                            f"old_content is required "
                            f"for existing file: "
                            f"{relative_path}"
                        )

                    if current_content != old_content:
                        raise ValueError(
                            "Stale change rejected for "
                            f"{relative_path}: "
                            "current file content does "
                            "not match old_content."
                        )
                elif old_content not in (
                    None,
                    "",
                ):
                    raise ValueError(
                        f"New file {relative_path} "
                        "must not contain old_content."
                    )

                self.write_file(
                    relative_path,
                    new_content,
                    iteration=iteration,
                )

                applied.append(
                    relative_path
                )

        except Exception as exc:
            record.status = "failed"

            return {
                "success": False,
                "code": "change_application_failed",
                "message": str(exc),
                "files_changed": applied,
            }

        record.status = "changes_applied"

        return {
            "success": True,
            "files_changed": applied,
        }

    def generate_and_apply(
        self,
        *,
        goal: str,
        iteration: int,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate and safely apply one bounded development
        iteration.
        """

        generated = self.generate_changes(
            goal=goal,
            iteration=iteration,
            context=context,
        )

        if not generated.get(
            "success",
            False,
        ):
            record = self._get_iteration(
                iteration
            )
            record.status = "failed"

            return generated

        changes = generated.get(
            "changes"
        )

        if not isinstance(
            changes,
            list,
        ):
            record = self._get_iteration(
                iteration
            )
            record.status = "failed"

            return {
                "success": False,
                "code": "invalid_provider_changes",
                "message": (
                    "Provider did not return a changes list."
                ),
            }

        return self.apply_changes(
            iteration=iteration,
            changes=changes,
        )

    def begin_iteration(
        self,
        number: int,
    ) -> DevelopmentIteration:
        if (
            number < 1
            or number > self.max_iterations
        ):
            raise ValueError(
                "Development iteration limit exceeded."
            )

        existing = next(
            (
                item
                for item in self.iterations
                if item.number == number
            ),
            None,
        )

        if existing is not None:
            return existing

        iteration = DevelopmentIteration(
            number=number,
            status="in_progress",
        )

        self.iterations.append(
            iteration
        )

        return iteration

    def run_validation(
        self,
        iteration: int,
        command: tuple[str, ...] = (
            "python",
            "-m",
            "pytest",
            "-q",
        ),
    ) -> DevelopmentIteration:
        record = self._get_iteration(
            iteration
        )

        if not self._is_allowed_command(
            command
        ):
            raise ValueError(
                "Validation command is not allowed: "
                f"{' '.join(command)}"
            )

        record.command = list(
            command
        )

        try:
            result = subprocess.run(
                list(command),
                cwd=self.boundary.workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )

        except subprocess.TimeoutExpired as exc:
            record.status = "failed"
            record.return_code = None
            record.output = (
                f"Validation timed out after "
                f"{self.timeout_seconds} seconds.\n"
                f"{exc}"
            )[-self.MAX_OUTPUT_CHARS :]

            return record

        output = "\n".join(
            value
            for value in (
                result.stdout,
                result.stderr,
            )
            if value
        )

        record.return_code = (
            result.returncode
        )

        record.output = (
            output[-self.MAX_OUTPUT_CHARS :]
        )

        record.status = (
            "completed"
            if result.returncode == 0
            else "failed"
        )

        return record

    def can_continue(
        self,
        iteration: int,
    ) -> bool:
        return (
            iteration
            < self.max_iterations
        )

    def result(
        self,
        iteration: int,
    ) -> dict[str, Any]:
        record = self._get_iteration(
            iteration
        )

        return {
            "iteration": record.number,
            "status": record.status,
            "files_changed": list(
                record.files_changed
            ),
            "command": list(
                record.command
            ),
            "return_code": record.return_code,
            "output": record.output,
            "can_continue": self.can_continue(
                record.number
            ),
        }

    def _get_iteration(
        self,
        number: int,
    ) -> DevelopmentIteration:
        record = next(
            (
                item
                for item in self.iterations
                if item.number == number
            ),
            None,
        )

        if record is None:
            raise ValueError(
                f"Development iteration "
                f"{number} has not been started."
            )

        return record

    def _is_allowed_command(
        self,
        command: tuple[str, ...],
    ) -> bool:
        return command in self.ALLOWED_COMMANDS
