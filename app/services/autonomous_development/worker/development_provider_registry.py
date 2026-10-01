from __future__ import annotations

from typing import Any

from app.services.autonomous_development.worker.development_provider import (
    DevelopmentProvider,
)


class DevelopmentProviderRegistry:
    """
    Registry for autonomous-development providers.

    Keeps provider selection separate from the autonomous
    development workflow itself.
    """

    def __init__(self) -> None:
        self._providers: dict[str, DevelopmentProvider] = {}

    def register(
        self,
        provider: DevelopmentProvider,
    ) -> None:
        if not isinstance(
            provider,
            DevelopmentProvider,
        ):
            raise TypeError(
                "Provider must implement DevelopmentProvider."
            )

        name = str(
            provider.name
        ).strip()

        if not name:
            raise ValueError(
                "Provider name cannot be empty."
            )

        self._providers[name] = provider

    def get(
        self,
        name: str,
    ) -> DevelopmentProvider | None:
        return self._providers.get(name)

    def remove(
        self,
        name: str,
    ) -> bool:
        return (
            self._providers.pop(
                name,
                None,
            )
            is not None
        )

    def clear(self) -> None:
        self._providers.clear()

    def list(self) -> list[str]:
        return sorted(
            self._providers.keys()
        )

    def has(
        self,
        name: str,
    ) -> bool:
        return name in self._providers

    def generate_changes(
        self,
        *,
        provider_name: str,
        goal: str,
        workspace: str,
        files: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider = self.get(
            provider_name
        )

        if provider is None:
            return {
                "success": False,
                "code": "provider_not_found",
                "provider": provider_name,
                "message": (
                    f"Development provider "
                    f"'{provider_name}' is not registered."
                ),
            }

        return provider.generate_changes(
            goal=goal,
            workspace=workspace,
            files=files,
            context=context,
        )
