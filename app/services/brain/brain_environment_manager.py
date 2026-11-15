"""Request-scoped environment resolution for Lumira Brain executions."""
from __future__ import annotations

from typing import Any

from app.services.brain.brain_config import BrainConfig, ConfigurationError
from app.services.brain.brain_context import BrainContext


class BrainEnvironmentError(ValueError):
    """Raised when an execution requests an unsupported environment."""


class BrainEnvironmentManager:
    """Resolve and create isolated execution contexts without mutating process state."""

    ENVIRONMENTS = frozenset({"development", "testing", "staging", "production"})
    ALIASES = {
        "dev": "development",
        "test": "testing",
        "stage": "staging",
        "prod": "production",
    }

    def __init__(self, config: BrainConfig | None = None) -> None:
        self.config = config or BrainConfig()

    @classmethod
    def normalize(cls, environment: str) -> str:
        if not isinstance(environment, str) or not environment.strip():
            raise BrainEnvironmentError("environment must be a non-empty string")
        normalized = environment.strip().lower()
        normalized = cls.ALIASES.get(normalized, normalized)
        if normalized not in cls.ENVIRONMENTS:
            raise BrainEnvironmentError("unsupported Lumira execution environment")
        return normalized

    def resolve(self, requested: str | None = None) -> str:
        """Explicit request environment wins; otherwise use config then development."""
        candidate = requested
        if candidate is None or (isinstance(candidate, str) and not candidate.strip()):
            try:
                candidate = self.config.get("LUMIRA_ENVIRONMENT", "development")
            except ConfigurationError as exc:
                raise BrainEnvironmentError("environment configuration is invalid") from exc
        return self.normalize(candidate)

    def create_context(
        self,
        *,
        environment: str | None = None,
        session_id: str = "",
        project_id: str = "",
        workspace: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> BrainContext:
        """Create a fresh context for one execution; no global state is shared."""
        if not isinstance(session_id, str) or not isinstance(project_id, str):
            raise BrainEnvironmentError("session and project identifiers must be strings")
        if not isinstance(workspace, str) or not workspace.strip():
            raise BrainEnvironmentError("workspace must be a non-empty string")
        if metadata is not None and not isinstance(metadata, dict):
            raise BrainEnvironmentError("context metadata must be an object")
        return BrainContext(
            session_id=session_id,
            project_id=project_id,
            environment=self.resolve(environment),
            workspace=workspace.strip(),
            metadata=dict(metadata or {}),
        )
