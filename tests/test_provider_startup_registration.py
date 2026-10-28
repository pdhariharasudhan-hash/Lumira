import pytest

from app.services.providers.openai_compatible_image_provider import OpenAICompatibleImageProvider
from app.services.providers.openai_compatible_speech_provider import OpenAICompatibleSpeechProvider
from app.services.providers.openai_compatible_transcription_provider import OpenAICompatibleTranscriptionProvider
from app.services.providers.openai_compatible_vision_provider import OpenAICompatibleVisionProvider
from app.services.providers.provider_registry import ProviderRegistry, PROVIDER_STATUS_NAMES
from app.services.providers.startup_registration import register_configured_providers


PROVIDER_ENV = {
    "LUMIRA_OLLAMA_SUMMARY_ENABLED": "0",
    "LUMIRA_TRANSCRIPTION_ENABLED": "0",
    "LUMIRA_TRANSCRIPTION_API_KEY": "",
    "LUMIRA_TRANSCRIPTION_BASE_URL": "https://api.openai.com/v1",
    "LUMIRA_TRANSCRIPTION_MODEL": "whisper-1",
    "LUMIRA_SPEECH_SYNTHESIS_ENABLED": "0",
    "LUMIRA_SPEECH_API_KEY": "",
    "LUMIRA_SPEECH_BASE_URL": "https://api.openai.com/v1",
    "LUMIRA_SPEECH_MODEL": "tts-1",
    "LUMIRA_SPEECH_VOICE": "alloy",
    "LUMIRA_IMAGE_GENERATION_ENABLED": "0",
    "LUMIRA_IMAGE_API_KEY": "",
    "LUMIRA_IMAGE_BASE_URL": "https://api.openai.com/v1",
    "LUMIRA_IMAGE_MODEL": "gpt-image-1",
    "LUMIRA_VISION_ENABLED": "0",
    "LUMIRA_VISION_API_KEY": "",
    "LUMIRA_VISION_BASE_URL": "https://api.openai.com/v1",
    "LUMIRA_VISION_MODEL": "gpt-4o-mini",
    "LUMIRA_RESEARCH_ENABLED": "0",
    "LUMIRA_RESEARCH_API_KEY": "",
    "LUMIRA_WAKE_WORD_ENABLED": "0",
    "LUMIRA_WAKE_WORD_API_KEY": "",
    "LUMIRA_WAKE_WORD_MODEL_PATH": "",
}


def _clear_optional_providers():
    for name in PROVIDER_STATUS_NAMES:
        ProviderRegistry.unregister(name)


def test_external_providers_are_registered_only_when_enabled_and_keyed(tmp_path, monkeypatch):
    previous = {name: ProviderRegistry.get(name) for name in PROVIDER_STATUS_NAMES}
    try:
        for key, value in PROVIDER_ENV.items():
            monkeypatch.setenv(key, value)
        model_path = tmp_path / "lumira.ppn"
        model_path.write_bytes(b"test-only model placeholder")
        monkeypatch.setenv("LUMIRA_WAKE_WORD_MODEL_PATH", str(model_path))

        _clear_optional_providers()
        register_configured_providers()
        assert not any(ProviderRegistry.get(name) is not None for name in PROVIDER_STATUS_NAMES)

        # An enable flag without credentials must not register external providers.
        for flag in (
            "LUMIRA_TRANSCRIPTION_ENABLED",
            "LUMIRA_SPEECH_SYNTHESIS_ENABLED",
            "LUMIRA_IMAGE_GENERATION_ENABLED",
            "LUMIRA_VISION_ENABLED",
            "LUMIRA_RESEARCH_ENABLED",
            "LUMIRA_WAKE_WORD_ENABLED",
        ):
            monkeypatch.setenv(flag, "1")
        _clear_optional_providers()
        register_configured_providers()
        assert not any(ProviderRegistry.get(name) is not None for name in PROVIDER_STATUS_NAMES)

        enabled_settings = {
            "LUMIRA_TRANSCRIPTION_ENABLED": "1",
            "LUMIRA_TRANSCRIPTION_API_KEY": "test-only",
            "LUMIRA_SPEECH_SYNTHESIS_ENABLED": "1",
            "LUMIRA_SPEECH_API_KEY": "test-only",
            "LUMIRA_IMAGE_GENERATION_ENABLED": "1",
            "LUMIRA_IMAGE_API_KEY": "test-only",
            "LUMIRA_VISION_ENABLED": "1",
            "LUMIRA_VISION_API_KEY": "test-only",
            "LUMIRA_RESEARCH_ENABLED": "1",
            "LUMIRA_RESEARCH_API_KEY": "test-only",
            "LUMIRA_WAKE_WORD_ENABLED": "1",
            "LUMIRA_WAKE_WORD_API_KEY": "test-only",
        }
        for key, value in enabled_settings.items():
            monkeypatch.setenv(key, value)

        monkeypatch.setenv("LUMIRA_WAKE_WORD_MODEL_PATH", str(tmp_path / "missing.ppn"))
        _clear_optional_providers()
        register_configured_providers()
        without_model = {name for name in PROVIDER_STATUS_NAMES if ProviderRegistry.get(name) is not None}
        assert without_model == {
            "transcription",
            "speech_synthesis",
            "image_generation",
            "image_understanding",
            "research",
        }

        monkeypatch.setenv("LUMIRA_WAKE_WORD_MODEL_PATH", str(model_path))
        _clear_optional_providers()
        register_configured_providers()
        registered = {name for name in PROVIDER_STATUS_NAMES if ProviderRegistry.get(name) is not None}
        assert registered == {
            "transcription",
            "speech_synthesis",
            "image_generation",
            "image_understanding",
            "research",
            "wake_word",
        }
    finally:
        _clear_optional_providers()
        for name, provider in previous.items():
            if provider is not None:
                ProviderRegistry.register(name, provider)


def test_invalid_optional_provider_config_does_not_break_other_providers(monkeypatch):
    previous = {name: ProviderRegistry.get(name) for name in PROVIDER_STATUS_NAMES}
    try:
        for key, value in PROVIDER_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("LUMIRA_TRANSCRIPTION_ENABLED", "1")
        monkeypatch.setenv("LUMIRA_TRANSCRIPTION_API_KEY", "test-only")
        monkeypatch.setenv("LUMIRA_IMAGE_GENERATION_ENABLED", "1")
        monkeypatch.setenv("LUMIRA_IMAGE_API_KEY", "test-only")
        monkeypatch.setenv("LUMIRA_IMAGE_BASE_URL", "https://api.openai.com:not-a-port/v1")

        _clear_optional_providers()
        register_configured_providers()

        assert ProviderRegistry.get("transcription") is not None
        assert ProviderRegistry.get("image_generation") is None
    finally:
        _clear_optional_providers()
        for name, provider in previous.items():
            if provider is not None:
                ProviderRegistry.register(name, provider)


def test_unexpected_optional_provider_error_does_not_break_startup(monkeypatch):
    previous = {name: ProviderRegistry.get(name) for name in PROVIDER_STATUS_NAMES}
    try:
        for key, value in PROVIDER_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("LUMIRA_TRANSCRIPTION_ENABLED", "1")
        monkeypatch.setenv("LUMIRA_TRANSCRIPTION_API_KEY", "test-only")
        monkeypatch.setenv("LUMIRA_IMAGE_GENERATION_ENABLED", "1")
        monkeypatch.setenv("LUMIRA_IMAGE_API_KEY", "test-only")
        monkeypatch.setattr(
            "app.services.providers.startup_registration.OpenAICompatibleTranscriptionProvider",
            lambda: (_ for _ in ()).throw(RuntimeError("private endpoint detail")),
        )

        _clear_optional_providers()
        register_configured_providers()

        assert ProviderRegistry.get("transcription") is None
        assert ProviderRegistry.get("image_generation") is not None
    finally:
        _clear_optional_providers()
        for name, provider in previous.items():
            if provider is not None:
                ProviderRegistry.register(name, provider)


def test_external_provider_constructors_reject_malformed_ports():
    invalid_url = "https://api.openai.com:not-a-port/v1"
    factories = (
        lambda: OpenAICompatibleTranscriptionProvider(
            api_key="test-only", base_url=invalid_url, model="test-model"
        ),
        lambda: OpenAICompatibleSpeechProvider(
            api_key="test-only", base_url=invalid_url, model="test-model", voice="test-voice"
        ),
        lambda: OpenAICompatibleImageProvider(
            api_key="test-only", base_url=invalid_url, model="test-model"
        ),
        lambda: OpenAICompatibleVisionProvider(
            api_key="test-only", base_url=invalid_url, model="test-model"
        ),
    )

    for factory in factories:
        with pytest.raises(ValueError):
            factory()



def test_local_transcription_takes_precedence_when_both_modes_are_enabled(monkeypatch):
    previous = {name: ProviderRegistry.get(name) for name in PROVIDER_STATUS_NAMES}
    local_provider = object()
    try:
        for key, value in PROVIDER_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("LUMIRA_TRANSCRIPTION_ENABLED", "1")
        monkeypatch.setenv("LUMIRA_TRANSCRIPTION_API_KEY", "test-only")
        monkeypatch.setenv("LUMIRA_LOCAL_TRANSCRIPTION_ENABLED", "1")
        monkeypatch.setattr(
            "app.services.providers.startup_registration.FasterWhisperTranscriptionProvider",
            lambda: local_provider,
        )

        _clear_optional_providers()
        register_configured_providers()

        assert ProviderRegistry.get("transcription") is local_provider
    finally:
        _clear_optional_providers()
        for name, provider in previous.items():
            if provider is not None:
                ProviderRegistry.register(name, provider)


def test_local_ollama_vision_takes_precedence_when_both_modes_are_enabled(monkeypatch):
    previous = {name: ProviderRegistry.get(name) for name in PROVIDER_STATUS_NAMES}
    local_provider = object()
    try:
        for key, value in PROVIDER_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("LUMIRA_VISION_ENABLED", "1")
        monkeypatch.setenv("LUMIRA_VISION_API_KEY", "test-only")
        monkeypatch.setenv("LUMIRA_OLLAMA_VISION_ENABLED", "1")
        monkeypatch.setattr(
            "app.services.providers.startup_registration.OllamaVisionProvider",
            lambda: local_provider,
        )

        _clear_optional_providers()
        register_configured_providers()

        assert ProviderRegistry.get("image_understanding") is local_provider
    finally:
        _clear_optional_providers()
        for name, provider in previous.items():
            if provider is not None:
                ProviderRegistry.register(name, provider)



def test_local_ollama_summary_registers_only_when_explicitly_enabled(monkeypatch):
    previous = {name: ProviderRegistry.get(name) for name in PROVIDER_STATUS_NAMES}
    local_provider = object()
    try:
        for key, value in PROVIDER_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("LUMIRA_OLLAMA_SUMMARY_ENABLED", "0")
        monkeypatch.setattr(
            "app.services.providers.startup_registration.OllamaSummaryProvider",
            lambda: local_provider,
        )
        _clear_optional_providers()
        register_configured_providers()
        assert ProviderRegistry.get("summarization") is None

        monkeypatch.setenv("LUMIRA_OLLAMA_SUMMARY_ENABLED", "1")
        _clear_optional_providers()
        register_configured_providers()
        assert ProviderRegistry.get("summarization") is local_provider
    finally:
        _clear_optional_providers()
        for name, provider in previous.items():
            if provider is not None:
                ProviderRegistry.register(name, provider)
