from __future__ import annotations

from app.services.providers.provider_registry import PROVIDER_STATUS_NAMES, ProviderRegistry


class ProviderReadinessService:
    """Report registration readiness without probing remote provider services."""

    def snapshot(self) -> dict:
        providers = {}
        available = 0
        for name in PROVIDER_STATUS_NAMES:
            registered = ProviderRegistry.get(name) is not None
            providers[name] = {
                "registered": registered,
                "status": "registered" if registered else "not_configured",
            }
            available += int(registered)
        return {
            "success": True,
            "status": "healthy" if available == len(PROVIDER_STATUS_NAMES) else "partial",
            "registered_count": available,
            "total_known_providers": len(PROVIDER_STATUS_NAMES),
            "providers": providers,
            "note": "Registration does not claim that an external or local provider is currently reachable.",
        }
