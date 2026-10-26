from fastapi import APIRouter

from app.services.providers.provider_registry import ProviderRegistry, PROVIDER_STATUS_NAMES

router = APIRouter()


@router.get("/providers/status")
def provider_status():
    """Report optional provider registration without exposing credentials or endpoints."""
    return {
        "providers": {
            name: {"registered": ProviderRegistry.get(name) is not None}
            for name in PROVIDER_STATUS_NAMES
        }
    }


@router.get("/health")
def health():
    """Return process health plus truthful optional-provider/security readiness."""
    providers = {
        name: {"registered": ProviderRegistry.get(name) is not None}
        for name in PROVIDER_STATUS_NAMES
    }

    return {
        "status": "ok",
        "services": {
            "validate": True,
            "builder": True,
            "execute": True,
            "code": True,
            "memory": True,
        },
        "providers": providers,
        "missing_optional_providers": [
            name for name, state in providers.items() if not state["registered"]
        ],
        "security": {
            "project_terminal_execution": "disabled",
            "sandbox_verification": "not_implemented",
        },
    }
