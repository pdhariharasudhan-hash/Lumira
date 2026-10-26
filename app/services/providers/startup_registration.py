"""Register optional integrations only when explicitly configured at startup."""

import logging
import os
from collections.abc import Callable

from app.services.providers.ollama_summary_provider import OllamaSummaryProvider
from app.services.providers.ollama_vision_provider import OllamaVisionProvider
from app.services.providers.openai_compatible_transcription_provider import OpenAICompatibleTranscriptionProvider
from app.services.providers.faster_whisper_transcription_provider import FasterWhisperTranscriptionProvider
from app.services.providers.openai_compatible_speech_provider import OpenAICompatibleSpeechProvider
from app.services.providers.openai_compatible_image_provider import OpenAICompatibleImageProvider
from app.services.providers.openai_compatible_vision_provider import OpenAICompatibleVisionProvider
from app.services.providers.tavily_research_provider import TavilyResearchProvider
from app.services.providers.picovoice_wake_word_provider import PicovoiceWakeWordProvider
from app.services.providers.provider_registry import ProviderRegistry


def _register_optional_provider(name: str, factory: Callable[[], object]) -> None:
    """Keep a malformed optional provider from preventing core app startup."""
    try:
        ProviderRegistry.register(name, factory())
    except Exception as exc:
        # Optional integrations must not prevent core startup, including when a
        # provider's optional dependency or SDK raises an unexpected exception.
        # Avoid logging exception text because provider configuration can contain
        # endpoint details. Readiness reports the provider as unavailable instead.
        logging.getLogger(__name__).warning(
            "Optional provider %s was not registered (%s).",
            name,
            type(exc).__name__,
        )


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def register_configured_providers() -> None:
    """Register configured providers; never make network calls during startup."""
    if _enabled("LUMIRA_OLLAMA_SUMMARY_ENABLED"):
        _register_optional_provider("summarization", OllamaSummaryProvider)

    if _enabled("LUMIRA_TRANSCRIPTION_ENABLED") and os.getenv("LUMIRA_TRANSCRIPTION_API_KEY", "").strip():
        _register_optional_provider("transcription", OpenAICompatibleTranscriptionProvider)

    # Local mode takes precedence when explicitly enabled; recordings remain on this machine.
    if _enabled("LUMIRA_LOCAL_TRANSCRIPTION_ENABLED"):
        _register_optional_provider("transcription", FasterWhisperTranscriptionProvider)

    if _enabled("LUMIRA_SPEECH_SYNTHESIS_ENABLED") and os.getenv("LUMIRA_SPEECH_API_KEY", "").strip():
        _register_optional_provider("speech_synthesis", OpenAICompatibleSpeechProvider)

    if _enabled("LUMIRA_IMAGE_GENERATION_ENABLED") and os.getenv("LUMIRA_IMAGE_API_KEY", "").strip():
        _register_optional_provider("image_generation", OpenAICompatibleImageProvider)

    if _enabled("LUMIRA_VISION_ENABLED") and os.getenv("LUMIRA_VISION_API_KEY", "").strip():
        _register_optional_provider("image_understanding", OpenAICompatibleVisionProvider)

    # Local Ollama vision takes precedence over the remote vision adapter when enabled.
    if _enabled("LUMIRA_OLLAMA_VISION_ENABLED"):
        _register_optional_provider("image_understanding", OllamaVisionProvider)

    if _enabled("LUMIRA_RESEARCH_ENABLED") and os.getenv("LUMIRA_RESEARCH_API_KEY", "").strip():
        _register_optional_provider("research", TavilyResearchProvider)

    model_path = os.getenv("LUMIRA_WAKE_WORD_MODEL_PATH", "").strip()
    if (
        _enabled("LUMIRA_WAKE_WORD_ENABLED")
        and os.getenv("LUMIRA_WAKE_WORD_API_KEY", "").strip()
        and model_path
        and os.path.isfile(model_path)
    ):
        _register_optional_provider("wake_word", PicovoiceWakeWordProvider)
