"""Register optional integrations only when explicitly configured at startup."""

import importlib
import logging
import os
from collections.abc import Callable

from app.services.providers.provider_registry import ProviderRegistry
from app.services.brain.brain_config import BrainConfig, ConfigurationError


def _lazy_provider(module_name: str, class_name: str) -> Callable[[], object]:
    """Create a provider only when its feature is enabled at startup."""
    def create_provider() -> object:
        module = importlib.import_module(module_name)
        provider_class = getattr(module, class_name)
        return provider_class()

    return create_provider


# These factories intentionally defer imports: optional SDKs and provider
# dependencies must not become requirements for importing the core app.
OllamaSummaryProvider = _lazy_provider(
    "app.services.providers.ollama_summary_provider", "OllamaSummaryProvider"
)
OllamaVisionProvider = _lazy_provider(
    "app.services.providers.ollama_vision_provider", "OllamaVisionProvider"
)
OpenAICompatibleTranscriptionProvider = _lazy_provider(
    "app.services.providers.openai_compatible_transcription_provider",
    "OpenAICompatibleTranscriptionProvider",
)
FasterWhisperTranscriptionProvider = _lazy_provider(
    "app.services.providers.faster_whisper_transcription_provider",
    "FasterWhisperTranscriptionProvider",
)
OpenAICompatibleSpeechProvider = _lazy_provider(
    "app.services.providers.openai_compatible_speech_provider", "OpenAICompatibleSpeechProvider"
)
WindowsSapiSpeechProvider = _lazy_provider(
    "app.services.providers.windows_sapi_speech_provider", "WindowsSapiSpeechProvider"
)
OpenAICompatibleImageProvider = _lazy_provider(
    "app.services.providers.openai_compatible_image_provider", "OpenAICompatibleImageProvider"
)
OpenAICompatibleVisionProvider = _lazy_provider(
    "app.services.providers.openai_compatible_vision_provider", "OpenAICompatibleVisionProvider"
)
TavilyResearchProvider = _lazy_provider(
    "app.services.providers.tavily_research_provider", "TavilyResearchProvider"
)
PicovoiceWakeWordProvider = _lazy_provider(
    "app.services.providers.picovoice_wake_word_provider", "PicovoiceWakeWordProvider"
)
YahooMarketDataProvider = _lazy_provider(
    "app.services.providers.yahoo_market_data_provider", "YahooMarketDataProvider"
)
LocalHttpDeviceTransport = _lazy_provider(
    "app.services.providers.local_http_device_transport", "LocalHttpDeviceTransport"
)


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
    """Read a feature flag through BrainConfig and fail closed on invalid values."""
    try:
        return BrainConfig().get_bool(name, default=False)
    except ConfigurationError:
        logging.getLogger(__name__).warning(
            "Optional provider configuration flag %s is invalid; provider disabled.",
            name,
        )
        return False


def register_configured_providers() -> None:
    """Register configured providers; never make network calls during startup."""
    if _enabled("LUMIRA_OLLAMA_SUMMARY_ENABLED"):
        _register_optional_provider("summarization", OllamaSummaryProvider)

    if _enabled("LUMIRA_TRANSCRIPTION_ENABLED") and (BrainConfig().get_secret("LUMIRA_TRANSCRIPTION_API_KEY") or ""):
        _register_optional_provider("transcription", OpenAICompatibleTranscriptionProvider)

    # Local mode takes precedence when explicitly enabled; recordings remain on this machine.
    if _enabled("LUMIRA_LOCAL_TRANSCRIPTION_ENABLED"):
        _register_optional_provider("transcription", FasterWhisperTranscriptionProvider)

    if _enabled("LUMIRA_SPEECH_SYNTHESIS_ENABLED") and (BrainConfig().get_secret("LUMIRA_SPEECH_API_KEY") or ""):
        _register_optional_provider("speech_synthesis", OpenAICompatibleSpeechProvider)

    # The built-in Windows voice engine is local and requires no API credentials.
    if os.name == "nt" and _enabled("LUMIRA_WINDOWS_SAPI_TTS_ENABLED"):
        _register_optional_provider("speech_synthesis", WindowsSapiSpeechProvider)

    if _enabled("LUMIRA_IMAGE_GENERATION_ENABLED") and (BrainConfig().get_secret("LUMIRA_IMAGE_API_KEY") or ""):
        _register_optional_provider("image_generation", OpenAICompatibleImageProvider)

    if _enabled("LUMIRA_VISION_ENABLED") and (BrainConfig().get_secret("LUMIRA_VISION_API_KEY") or ""):
        _register_optional_provider("image_understanding", OpenAICompatibleVisionProvider)

    # Local Ollama vision takes precedence over the remote vision adapter when enabled.
    if _enabled("LUMIRA_OLLAMA_VISION_ENABLED"):
        _register_optional_provider("image_understanding", OllamaVisionProvider)

    if _enabled("LUMIRA_RESEARCH_ENABLED") and (BrainConfig().get_secret("LUMIRA_RESEARCH_API_KEY") or ""):
        _register_optional_provider("research", TavilyResearchProvider)

    if _enabled("LUMIRA_MARKET_DATA_ENABLED"):
        _register_optional_provider("market_data", YahooMarketDataProvider)

    # Explicit opt-in; endpoints are stored per device and must be private IPs.
    if _enabled("LUMIRA_LOCAL_HTTP_DEVICE_TRANSPORT_ENABLED"):
        _register_optional_provider("device_transport", LocalHttpDeviceTransport)

    model_path = str(BrainConfig().get("LUMIRA_WAKE_WORD_MODEL_PATH", "")).strip()
    if (
        _enabled("LUMIRA_WAKE_WORD_ENABLED")
        and (BrainConfig().get_secret("LUMIRA_WAKE_WORD_API_KEY") or "")
        and model_path
        and os.path.isfile(model_path)
    ):
        _register_optional_provider("wake_word", PicovoiceWakeWordProvider)
