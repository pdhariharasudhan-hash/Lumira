from app.routes import health as health_route
from app.services.providers.provider_registry import ProviderRegistry
from app.services.providers.startup_registration import register_configured_providers
from app.services.providers.windows_sapi_speech_provider import WindowsSapiSpeechProvider


def test_windows_sapi_provider_registers_only_when_explicitly_enabled(monkeypatch):
    ProviderRegistry.unregister("speech_synthesis")
    for name in (
        "LUMIRA_SPEECH_SYNTHESIS_ENABLED",
        "LUMIRA_SPEECH_API_KEY",
        "LUMIRA_WINDOWS_SAPI_TTS_ENABLED",
        "LUMIRA_OLLAMA_SUMMARY_ENABLED",
        "LUMIRA_TRANSCRIPTION_ENABLED",
        "LUMIRA_TRANSCRIPTION_API_KEY",
        "LUMIRA_LOCAL_TRANSCRIPTION_ENABLED",
        "LUMIRA_IMAGE_GENERATION_ENABLED",
        "LUMIRA_IMAGE_API_KEY",
        "LUMIRA_VISION_ENABLED",
        "LUMIRA_VISION_API_KEY",
        "LUMIRA_OLLAMA_VISION_ENABLED",
        "LUMIRA_RESEARCH_ENABLED",
        "LUMIRA_RESEARCH_API_KEY",
        "LUMIRA_MARKET_DATA_ENABLED",
        "LUMIRA_LOCAL_HTTP_DEVICE_TRANSPORT_ENABLED",
        "LUMIRA_WAKE_WORD_ENABLED",
        "LUMIRA_WAKE_WORD_API_KEY",
        "LUMIRA_WAKE_WORD_MODEL_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

    try:
        register_configured_providers()
        assert ProviderRegistry.get("speech_synthesis") is None

        monkeypatch.setenv("LUMIRA_WINDOWS_SAPI_TTS_ENABLED", "true")
        register_configured_providers()
        provider = ProviderRegistry.get("speech_synthesis")
        assert isinstance(provider, WindowsSapiSpeechProvider)
        assert provider.provider_scope == "local"

        status = health_route.provider_status()["providers"]["speech_synthesis"]
        assert status["registered"] is True
        assert status["configured"] is True
        assert status["execution_mode"] == "local"
        assert status["provider_scope"] == "local"
    finally:
        ProviderRegistry.unregister("speech_synthesis")
