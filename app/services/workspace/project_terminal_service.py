from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.projects.project_paths import resolve_project_path
from app.services.workspace.container_sandbox_provider import ContainerSandboxProvider


class ProjectTerminalService:
    """Allowlisted validation runner; not an operating-system sandbox."""

    # Keep this false until execution is isolated by a real OS security boundary.
    # The flag alone is never proof that an OS sandbox exists.
    OS_SANDBOX_ENABLED = True

    def __init__(self, root: str | Path = "memory/project_terminal_runs.json", sandbox=None):
        self.store = AtomicJsonStore(root)
        self.sandbox = sandbox or ContainerSandboxProvider()

    def _os_sandbox_verified(self) -> bool:
        """Execution is enabled only when a concrete isolation provider verifies itself."""
        try:
            status = self.sandbox.status()
            return bool(getattr(status, "available", False))
        except Exception:
            return False

    COMMANDS: dict[str, tuple[str, ...]] = {
        "pytest": ("python", "-m", "pytest", "-q"),
        "compileall": ("python", "-m", "compileall", "app"),
        "npm_test": ("npm", "test", "--", "--run"),
        "npm_build": ("npm", "run", "build"),
    }
    MAX_OUTPUT = 20_000
    MAX_RUNS = 100
    TIMEOUT_SECONDS = 120

    @staticmethod
    def _require_runs(data: Any) -> list:
        if not isinstance(data, list):
            raise PersistenceIntegrityError("Project terminal run history must contain a list of records")
        return data

    def list_commands(self) -> dict[str, list[str]]:
        return {name: list(command) for name, command in self.COMMANDS.items()}

    def run(
        self,
        project: str,
        version: str,
        command_id: str,
        *,
        trusted_project: bool = False,
    ) -> dict[str, Any]:
        if not self._os_sandbox_verified():
            try:
                sandbox_reason = self.sandbox.status().reason
            except Exception:
                sandbox_reason = "sandbox verification unavailable"
            return {
                "success": False,
                "code": "project_execution_disabled",
                "sandbox_reason": sandbox_reason,
                "message": (
                    "Project command execution is disabled because no OS-level sandbox "
                    "is configured. Environment flags and UI confirmation cannot provide "
                    "process isolation. This feature will remain disabled until a real "
                    "sandbox is implemented and verified."
                ),
            }
        if trusted_project is not True:
            return {
                "success": False,
                "code": "trust_confirmation_required",
                "message": (
                    "Execution requires explicit confirmation that this generated "
                    "project is trusted. The allowlisted runner is not an OS sandbox."
                ),
            }

        command = self.COMMANDS.get(command_id)
        if command is None:
            return {"success": False, "code": "command_not_allowed",
                    "message": "Only the configured validation commands are available."}

        project_path = resolve_project_path(project, version)
        if project_path is None or not project_path.is_dir():
            return {"success": False, "code": "project_not_found",
                    "message": "Project version was not found."}

        root = Path("generated").resolve()
        if root not in project_path.resolve().parents:
            return {"success": False, "code": "project_boundary_violation",
                    "message": "Project path is outside the generated workspace."}

        started = datetime.now(UTC).isoformat()
        try:
            # The provider may wrap subprocess execution; keep the allowlisted
            # invocation explicit so startup failures are classified accurately.
            result = self.sandbox.run(
                command, project_path, timeout=self.TIMEOUT_SECONDS
            )
            output = "\n".join(x for x in (result.stdout, result.stderr) if x)
            record = {
                "project": project, "version": version, "command": list(command),
                "command_id": command_id, "started_at": started,
                "completed_at": datetime.now(UTC).isoformat(),
                "return_code": result.returncode, "status": "completed" if result.returncode == 0 else "failed",
                "output": output[-self.MAX_OUTPUT:],
            }
        except subprocess.TimeoutExpired as exc:
            record = {
                "project": project, "version": version, "command": list(command),
                "command_id": command_id, "started_at": started,
                "completed_at": datetime.now(UTC).isoformat(),
                "return_code": None, "status": "timeout",
                "output": str(exc)[-self.MAX_OUTPUT:],
            }
        except (OSError, RuntimeError) as exc:
            # Provider exceptions may contain local paths or machine details.
            return {
                "success": False,
                "code": "terminal_execution_failed",
                "message": "The project validation command could not be started.",
                "error_type": type(exc).__name__,
            }

        def mutate(data: Any) -> Any:
            runs = self._require_runs(data)
            runs.append(record)
            return runs[-self.MAX_RUNS:]

        self.store.update(mutate, default=[])
        return {"success": record["status"] == "completed" and record["return_code"] == 0,
                "run": record}

    def list_runs(self, project: str | None = None, version: str | None = None) -> list[dict[str, Any]]:
        data = self._require_runs(self.store.read([]))
        return [item for item in data if isinstance(item, dict)
                and (project is None or item.get("project") == project)
                and (version is None or item.get("version") == version)]
