from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SandboxStatus:
    available: bool
    provider: str | None
    reason: str


class ContainerSandboxProvider:
    """Optional container boundary for generated-project validation.

    This provider never enables execution unless Docker is installed and the
    caller supplies an explicit sandbox image. Generated projects are mounted
    read-only and commands run without network access or Linux capabilities.
    """

    DEFAULT_IMAGE = "python:3.12-slim"

    def status(self) -> SandboxStatus:
        docker = shutil.which("docker")
        if not docker:
            return SandboxStatus(False, None, "docker_not_installed")
        try:
            result = subprocess.run(
                [docker, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return SandboxStatus(False, None, "docker_unavailable")
        if result.returncode != 0 or not result.stdout.strip():
            return SandboxStatus(False, None, "docker_daemon_unavailable")
        return SandboxStatus(True, "docker", "verified")

    def run(
        self,
        command: tuple[str, ...],
        project_path: Path,
        *,
        timeout: int,
        image: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        status = self.status()
        if not status.available:
            raise RuntimeError(status.reason)
        docker = shutil.which("docker")
        assert docker is not None
        image = image or self.DEFAULT_IMAGE
        # No shell is used. The project is read-only, networking is disabled,
        # privileges/capabilities are dropped, and temporary writes use tmpfs.
        argv = [
            docker, "run", "--rm", "--network", "none",
            "--read-only", "--cap-drop", "ALL",
            "--pids-limit", "128", "--memory", "1g",
            "--cpus", "1.0", "--security-opt", "no-new-privileges",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m",
            "-v", f"{project_path.resolve()}:/workspace:ro",
            "-w", "/workspace", image, *command,
        ]
        return subprocess.run(
            argv, capture_output=True, text=True,
            timeout=timeout, shell=False,
        )
