"""Health and safe diagnostics for Lumira's optional providers."""

import os
from typing import Any

from fastapi import APIRouter

from app.services.providers.provider_registry import ProviderRegistry, PROVIDER_STATUS_NAMES
from app.services.providers.provider_access_policy_service import ProviderAccessPolicyService

router = APIRouter()

# Environment-variable names only; never return secret values or endpoint URLs.
_PROVIDER_ENABLE_FLAGS = {
    "summarization": ("LUMIRA_OLLAMA_SUMMARY_ENABLED",),
    "transcription": ("LUMIRA_TRANSCRIPTION_ENABLED", "LUMIRA_LOCAL_TRANSCRIPTION_ENABLED"),
    "speech_synthesis": ("LUMIRA_SPEECH_SYNTHESIS_ENABLED", "LUMIRA_WINDOWS_SAPI_TTS_ENABLED"),
    "image_generation": ("LUMIRA_IMAGE_GENERATION_ENABLED",),
    "video_generation": ("LUMIRA_VIDEO_GENERATION_ENABLED",),
    "image_understanding": ("LUMIRA_VISION_ENABLED", "LUMIRA_OLLAMA_VISION_ENABLED"),
    "research": ("LUMIRA_RESEARCH_ENABLED",),
    "wake_word": ("LUMIRA_WAKE_WORD_ENABLED",),
    "device_transport": (),
}


def _flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _provider_state(name: str) -> dict[str, Any]:
    """Describe registration/configuration without claiming a provider is reachable."""
    provider = ProviderRegistry.get(name)
    flags = _PROVIDER_ENABLE_FLAGS.get(name, ())
    configured = any(_flag_enabled(flag) for flag in flags)
    state: dict[str, Any] = {
        "registered": provider is not None,
        "configured": configured,
        "availability": "registered" if provider is not None else "not_registered",
        "provider_scope": (
            ProviderAccessPolicyService.provider_scope(provider)
            if provider is not None
            else None
        ),
        # This endpoint deliberately does not perform provider calls.
        "reachable": None,
        "last_success": None,
    }
    if provider is not None:
        implementation = type(provider).__name__
        state["implementation"] = implementation
        state["execution_mode"] = "local" if implementation in {
            "FasterWhisperTranscriptionProvider",
            "OllamaVisionProvider",
            "OllamaSummaryProvider",
            "WindowsSapiSpeechProvider",
        } else "remote_or_external"
        # Model identifiers are useful diagnostics; endpoint URLs, API keys, and paths are omitted.
        model = getattr(provider, "model_name", None) or getattr(provider, "model", None)
        if isinstance(model, str) and model and len(model) <= 160:
            state["model"] = model
    return state


def _all_provider_states() -> dict[str, dict[str, Any]]:
    return {name: _provider_state(name) for name in PROVIDER_STATUS_NAMES}


@router.get("/providers/status")
def provider_status():
    """Report safe provider configuration and registration details.

    Registration does not guarantee that a model is installed or a remote service is
    reachable; those checks are deliberately not performed by this lightweight endpoint.
    """
    providers = _all_provider_states()
    return {
        "capabilities": {
            "memory": True,
            "voice_capture": True,
            "artifact_manager": True,
            "unified_search": True,
            "sessions": True,
        },
        "providers": providers,
        "registered_count": sum(state["registered"] for state in providers.values()),
        "configured_but_unregistered": [
            name for name, state in providers.items()
            if state["configured"] and not state["registered"]
        ],
    }


@router.get("/health")
def health():
    """Return process health plus truthful optional-provider/security readiness."""
    providers = _all_provider_states()
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
