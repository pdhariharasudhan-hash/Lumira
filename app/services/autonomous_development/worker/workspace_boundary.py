from __future__ import annotations

from pathlib import Path


class WorkspaceBoundaryError(ValueError):
    """Raised when an autonomous development operation leaves the workspace."""


class WorkspaceBoundary:
    """
    Safety boundary for autonomous development.

    All filesystem operations must remain inside the configured repository.
    """

    FORBIDDEN_NAMES = {
        ".git",
        ".env",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
    }

    FORBIDDEN_FILES = {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
    }

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()

        if not self.workspace.exists():
            raise WorkspaceBoundaryError(
                f"Workspace does not exist: {self.workspace}"
            )

        if not self.workspace.is_dir():
            raise WorkspaceBoundaryError(
                f"Workspace is not a directory: {self.workspace}"
            )

    def resolve(self, relative_path: str | Path) -> Path:
        candidate = (self.workspace / relative_path).resolve()

        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise WorkspaceBoundaryError(
                f"Path escapes workspace: {relative_path}"
            ) from exc

        self._validate_path(candidate)
        return candidate

    def exists(self, relative_path: str | Path) -> bool:
        return self.resolve(relative_path).exists()

    def read_text(self, relative_path: str | Path) -> str:
        path = self.resolve(relative_path)

        if not path.is_file():
            raise WorkspaceBoundaryError(
                f"Workspace file does not exist: {relative_path}"
            )

        return path.read_text(encoding="utf-8")

    def write_text(self, relative_path: str | Path, content: str) -> Path:
        if not isinstance(content, str):
            raise WorkspaceBoundaryError("File content must be text.")

        path = self.resolve(relative_path)

        if path.exists() and not path.is_file():
            raise WorkspaceBoundaryError(
                f"Cannot overwrite non-file path: {relative_path}"
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        return path

    def list_files(self, relative_path: str | Path = ".") -> list[str]:
        root = self.resolve(relative_path)

        if not root.is_dir():
            raise WorkspaceBoundaryError(
                f"Workspace directory does not exist: {relative_path}"
            )

        files: list[str] = []

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            try:
                path.relative_to(self.workspace)
            except ValueError:
                continue

            if self._is_forbidden(path):
                continue

            files.append(str(path.relative_to(self.workspace)))

        return sorted(files)

    def _validate_path(self, path: Path) -> None:
        if self._is_forbidden(path):
            raise WorkspaceBoundaryError(
                f"Access to protected workspace path is not allowed: {path}"
            )

    def _is_forbidden(self, path: Path) -> bool:
        relative = path.relative_to(self.workspace)

        if any(part in self.FORBIDDEN_NAMES for part in relative.parts):
            return True

        if path.name in self.FORBIDDEN_FILES:
            return True

        return False
