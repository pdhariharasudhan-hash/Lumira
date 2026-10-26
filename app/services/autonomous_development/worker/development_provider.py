from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DevelopmentProvider(ABC):
    """
    Provider contract for autonomous source-code development.

    A provider receives a development request and returns
    structured file changes. The autonomous-development layer
    remains responsible for validation, safety, application,
    testing, recovery, and verification.
    """

    name = "development_provider"

    @abstractmethod
    def generate_changes(
        self,
        *,
        goal: str,
        workspace: str,
        files: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate bounded source-file changes.

        Expected result:

        {
            "success": True,
            "changes": [
                {
                    "path": "...",
                    "old_content": "...",
                    "new_content": "...",
                    "reason": "..."
                }
            ]
        }
        """
        raise NotImplementedError
