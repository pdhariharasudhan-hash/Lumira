from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.autonomous_development.worker.development_provider import (
    DevelopmentProvider,
)
from app.services.autonomous_development.worker.development_provider_registry import (
    DevelopmentProviderRegistry,
)
from app.services.autonomous_development.worker.openai_compatible_provider import (
    OpenAICompatibleDevelopmentProvider,
)


class DevelopmentCodeGenerator:
    """
    Coordinates autonomous source-code generation.

    The generator owns provider registration and selection.
    Providers generate changes only; application and validation
    remain controlled by the autonomous-development system.
    """

    DEFAULT_PROVIDER = "openai_compatible"
    MAX_PROVIDER_FALLBACKS = 2

    def __init__(
        self,
        workspace: str | Path = ".",
        registry: DevelopmentProviderRegistry | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()

        self.registry = (
            registry
            or DevelopmentProviderRegistry()
        )

        if not self.registry.has(
            self.DEFAULT_PROVIDER
        ):
            self.registry.register(
                OpenAICompatibleDevelopmentProvider()
            )

    def register_provider(
        self,
        provider: DevelopmentProvider,
    ) -> None:
        self.registry.register(
            provider
        )

    def generate_changes(
        self,
        *,
        goal: str,
        files: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
        provider_name: str | None = None,
    ) -> dict[str, Any]:
        selected_provider = (
            provider_name
            or self.DEFAULT_PROVIDER
        )
        candidates = [selected_provider]
        if provider_name is None:
            candidates.extend(
                name
                for name in self.registry.list()
                if name != selected_provider
            )
            candidates = candidates[: self.MAX_PROVIDER_FALLBACKS + 1]

        errors = []
        for name in candidates:
            result = self.registry.generate_changes(
                provider_name=name,
                goal=goal,
                workspace=str(self.workspace),
                files=files,
                context=context,
            )
            if result.get("success") or result.get("code") == "provider_no_change":
                return result
            errors.append({"provider": name, "code": result.get("code")})

        if len(candidates) == 1:
            return result
        return {
            "success": False,
            "code": "provider_failover_exhausted",
            "providers_attempted": [item["provider"] for item in errors],
            "provider_errors": errors,
            "message": "No configured development provider produced a usable response.",
        }
