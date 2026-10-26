from __future__ import annotations

import pytest

from app.services.providers.openai_compatible_speech_provider import OpenAICompatibleSpeechProvider
from app.services.resources.resource_budget_service import ResourceBudgetService


def test_speech_synthesis_defers_under_memory_pressure(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "critical",
            "defer_optional_heavy_media_work": True,
        },
    )

    def forbidden_request(*args, **kwargs):
        raise AssertionError("speech API must not be called while media work is deferred")

    monkeypatch.setattr("requests.post", forbidden_request)
    provider = OpenAICompatibleSpeechProvider(api_key="test-key")

    with pytest.raises(RuntimeError, match="deferred"):
        provider.synthesize("Hello from Lumira", "en")


def test_speech_synthesis_rejects_unsupported_language_before_request(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "normal",
            "defer_optional_heavy_media_work": False,
        },
    )

    def forbidden_request(*args, **kwargs):
        raise AssertionError("unsupported language must not reach the API")

    monkeypatch.setattr("requests.post", forbidden_request)
    provider = OpenAICompatibleSpeechProvider(api_key="test-key")

    with pytest.raises(ValueError, match="language"):
        provider.synthesize("Hello from Lumira", "fr")

from app.services.providers.openai_compatible_transcription_provider import OpenAICompatibleTranscriptionProvider


def test_transcription_defers_under_memory_pressure(tmp_path, monkeypatch):
    audio = tmp_path / "capture.wav"
    audio.write_bytes(b"RIFF" + b"\\x00" * 12)

    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "constrained",
            "defer_optional_heavy_media_work": True,
        },
    )

    def forbidden_request(*args, **kwargs):
        raise AssertionError("transcription API must not be called while deferred")

    monkeypatch.setattr("requests.post", forbidden_request)
    provider = OpenAICompatibleTranscriptionProvider(api_key="test-key")

    with pytest.raises(RuntimeError, match="deferred"):
        provider.transcribe(str(audio))
