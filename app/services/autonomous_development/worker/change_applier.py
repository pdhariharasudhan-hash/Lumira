from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .workspace_boundary import WorkspaceBoundary


@dataclass(frozen=True)
class FileChange:
    path: str
    old_content: str | None
    new_content: str
    reason: str


class ChangeValidationError(ValueError):
    """Raised when an autonomous file change is unsafe or invalid."""


class ChangeApplier:
    """
    Applies explicitly described file changes through WorkspaceBoundary.

    A change must match the current file contents when old_content is
    provided. This prevents stale autonomous plans from silently
    overwriting newer work.
    """

    MAX_CHANGES = 20
    MAX_FILE_SIZE = 500_000

    def __init__(self, boundary: WorkspaceBoundary) -> None:
        self.boundary = boundary

    def validate(
        self,
        changes: list[FileChange],
    ) -> list[FileChange]:
        if not isinstance(changes, list):
            raise ChangeValidationError("Changes must be a list.")

        if len(changes) > self.MAX_CHANGES:
            raise ChangeValidationError(
                f"A development iteration may contain at most "
                f"{self.MAX_CHANGES} file changes."
            )

        validated: list[FileChange] = []

        for change in changes:
            if not isinstance(change, FileChange):
                raise ChangeValidationError(
                    "Every change must be a FileChange."
                )

            if not change.path.strip():
                raise ChangeValidationError(
                    "Change path cannot be empty."
                )

            if not change.reason.strip():
                raise ChangeValidationError(
                    f"Change reason is required: {change.path}"
                )

            if not isinstance(change.new_content, str):
                raise ChangeValidationError(
                    f"New content must be text: {change.path}"
                )

            if len(change.new_content) > self.MAX_FILE_SIZE:
                raise ChangeValidationError(
                    f"New content is too large: {change.path}"
                )

            path = self.boundary.resolve(change.path)

            if path.exists() and not path.is_file():
                raise ChangeValidationError(
                    f"Target is not a file: {change.path}"
                )

            if path.exists():
                if not isinstance(change.old_content, str):
                    raise ChangeValidationError(
                        f"old_content is required for existing file: {change.path}"
                    )
                current = self.boundary.read_text(change.path)

                if current != change.old_content:
                    raise ChangeValidationError(
                        f"File changed since planning: {change.path}"
                    )
            elif change.old_content not in (None, ""):
                raise ChangeValidationError(
                    f"Expected existing file was not found: {change.path}"
                )

            validated.append(change)

        return validated

    def apply(
        self,
        changes: list[FileChange],
    ) -> list[str]:
        validated = self.validate(changes)

        changed_files: list[str] = []

        for change in validated:
            self.boundary.write_text(
                change.path,
                change.new_content,
            )
            changed_files.append(change.path)

        return changed_files

    @staticmethod
    def from_dict(value: dict[str, Any]) -> FileChange:
        if not isinstance(value, dict):
            raise ChangeValidationError(
                "File change must be an object."
            )

        required = {"path", "new_content", "reason"}

        missing = required - value.keys()

        if missing:
            raise ChangeValidationError(
                f"File change is missing fields: {sorted(missing)}"
            )

        old_content = value.get("old_content")

        if old_content is not None and not isinstance(old_content, str):
            raise ChangeValidationError(
                "old_content must be text or null."
            )

        return FileChange(
            path=str(value["path"]),
            old_content=old_content,
            new_content=str(value["new_content"]),
            reason=str(value["reason"]),
        )
