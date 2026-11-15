from __future__ import annotations

import shutil
from app.services.workspace.sandbox_provider_factory import create_sandbox_provider


class SandboxReadinessService:
    """Read-only status for the project execution boundary."""

    def __init__(self, sandbox=None):
        self.sandbox = sandbox if sandbox is not None else create_sandbox_provider()

    def snapshot(self) -> dict:
        status = self.sandbox.status()
        available = bool(status.available)
        return {
            # Provider availability is only a host prerequisite probe. It is not
            # evidence that a disposable guest has executed and shut down safely.
            "success": available,
            "status": "prerequisites_available" if available else "blocked",
            "provider": status.provider,
            "reason": status.reason,
            "docker_detected": bool(shutil.which("docker")),
            "execution_policy": "fail_closed",
            "execution_enabled": False,
            "live_execution_verified": False,
            "network": "configured_disabled_not_live_verified",
            "project_mount": "configured_read_only_not_live_verified",
        }
