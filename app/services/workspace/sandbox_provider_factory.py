from __future__ import annotations

import sys
from typing import Protocol

from app.services.workspace.container_sandbox_provider import (
    ContainerSandboxProvider,
)
from app.services.workspace.windows_sandbox_provider import WindowsSandboxProvider


class SandboxProvider(Protocol):
    def status(self): ...

    def run(self, command, project_path, *, timeout: int): ...


def create_sandbox_provider(platform: str | None = None) -> SandboxProvider:
    """Select the host's supported isolated execution provider.

    Selection does not enable execution. ProjectTerminalService keeps a second
    hard gate that requires explicit configuration and a verified provider.
    """
    selected_platform = sys.platform if platform is None else platform
    if selected_platform == "win32":
        return WindowsSandboxProvider()
    return ContainerSandboxProvider()
