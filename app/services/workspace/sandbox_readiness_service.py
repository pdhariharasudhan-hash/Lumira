from __future__ import annotations

import shutil
from app.services.workspace.container_sandbox_provider import ContainerSandboxProvider


class SandboxReadinessService:
    """Read-only status for the project execution boundary."""

    def __init__(self, sandbox=None):
        self.sandbox = sandbox or ContainerSandboxProvider()

    def snapshot(self) -> dict:
        status = self.sandbox.status()
        return {
            "success": bool(status.available),
            "status": "verified" if status.available else "blocked",
            "provider": status.provider,
            "reason": status.reason,
            "docker_detected": bool(shutil.which("docker")),
            "execution_policy": "fail_closed",
            "network": "disabled_per_run",
            "project_mount": "read_only",
        }
