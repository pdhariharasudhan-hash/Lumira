import json

import pytest
import requests

from app.services.providers.openai_compatible_transcription_provider import (
    OpenAICompatibleTranscriptionProvider,
)
from app.services.resources.resource_budget_service import ResourceBudgetService


@pytest.fixture(autouse=True)
def normal_resource_budget(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {"defer_optional_heavy_media_work": False, "resource_pressure": "normal"},
    )


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        assert chunk_size == 64 * 1024
        yield self.body

    def close(self):
        self.closed = True


def test_provider_sends_bounded_authenticated_multipart_request(tmp_path, monkeypatch):
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        response = FakeResponse({"text": "வணக்கம் Lumira"})
        captured["response"] = response
        return response

    monkeypatch.setattr(requests, "post", fake_post)
    provider = OpenAICompatibleTranscriptionProvider(api_key="test-secret", timeout=999)
    assert provider.transcribe(str(audio)) == "வணக்கம் Lumira"
    assert captured["url"] == "https://api.openai.com/v1/audio/transcriptions"
    assert captured["headers"]["Authorization"] == "Bearer test-secret"
    assert captured["data"] == {"model": "whisper-1", "response_format": "json"}
    assert captured["timeout"] == 120
    assert captured["stream"] is True
    assert captured["response"].closed is True
    assert captured["files"]["file"][0] == "voice.wav"
    assert captured["files"]["file"][2] == "audio/wav"
    captured["files"]["file"][1].close()


def test_provider_accepts_webm_and_uses_webm_content_type():
    assert "webm" in OpenAICompatibleTranscriptionProvider.SUPPORTED_EXTENSIONS
    assert OpenAICompatibleTranscriptionProvider._content_type("webm") == "video/webm"


def test_provider_requires_key_and_rejects_unsafe_url():
    with pytest.raises(RuntimeError, match="API key"):
        OpenAICompatibleTranscriptionProvider(api_key="").transcribe("missing.wav")
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAICompatibleTranscriptionProvider(api_key="x", base_url="http://example.com/v1")
    with pytest.raises(ValueError, match="invalid"):
        OpenAICompatibleTranscriptionProvider(api_key="x", base_url="https://user:pass@example.com/v1")


def test_provider_validates_file_extension_size_and_empty_output(tmp_path, monkeypatch):
    unsupported = tmp_path / "voice.ogg"
    unsupported.write_bytes(b"audio")
    provider = OpenAICompatibleTranscriptionProvider(api_key="x")
    with pytest.raises(ValueError, match="format"):
        provider.transcribe(str(unsupported))

    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty or exceeds"):
        provider.transcribe(str(empty))

    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse({"text": "  "}))
    with pytest.raises(ValueError, match="empty transcript"):
        provider.transcribe(str(audio))


def test_provider_sanitizes_request_and_invalid_json_errors(tmp_path, monkeypatch):
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    provider = OpenAICompatibleTranscriptionProvider(api_key="secret-value")

    def failed_request(*_args, **_kwargs):
        raise requests.ConnectionError("secret-value leaked")

    monkeypatch.setattr(requests, "post", failed_request)
    with pytest.raises(RuntimeError) as error:
        provider.transcribe(str(audio))
    assert "secret-value" not in str(error.value)

    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse(["invalid-shape"]))
    with pytest.raises(ValueError, match="empty transcript"):
        provider.transcribe(str(audio))


def test_provider_rejects_oversized_audio_and_transcript(tmp_path, monkeypatch):
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"a" * (OpenAICompatibleTranscriptionProvider.MAX_AUDIO_BYTES + 1))
    provider = OpenAICompatibleTranscriptionProvider(api_key="x")
    with pytest.raises(ValueError, match="size limit"):
        provider.transcribe(str(audio))

    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse({"text": "x" * (provider.MAX_TRANSCRIPT_CHARS + 1)}))
    with pytest.raises(ValueError, match="transcript size limit"):
        provider.transcribe(str(audio))

    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse({"text": "x" * provider.MAX_RESPONSE_BYTES}))
    with pytest.raises(ValueError, match="response size limit"):
        provider.transcribe(str(audio))
