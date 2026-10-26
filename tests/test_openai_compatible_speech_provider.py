import pytest
import requests

from app.services.providers.openai_compatible_speech_provider import OpenAICompatibleSpeechProvider


class FakeResponse:
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        assert chunk_size == 64 * 1024
        yield from self.chunks

    def close(self):
        self.closed = True


def test_speech_provider_sends_bounded_authenticated_request(monkeypatch):
    response = FakeResponse([b"ID3", b"fake-mp3-bytes"])
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response

    monkeypatch.setattr(requests, "post", fake_post)
    provider = OpenAICompatibleSpeechProvider(api_key="test-secret", timeout=999)
    result = provider.synthesize("வணக்கம் Lumira", "ta-en")

    assert result == {"success": True, "content": b"ID3fake-mp3-bytes", "extension": "mp3"}
    assert captured["url"] == "https://api.openai.com/v1/audio/speech"
    assert captured["headers"]["Authorization"] == "Bearer test-secret"
    assert captured["json"] == {"model": "tts-1", "voice": "alloy", "input": "வணக்கம் Lumira", "response_format": "mp3"}
    assert captured["timeout"] == 120
    assert captured["stream"] is True
    assert response.closed is True


def test_speech_provider_requires_key_and_rejects_unsafe_url():
    with pytest.raises(RuntimeError, match="API key"):
        OpenAICompatibleSpeechProvider(api_key="").synthesize("hello", "en")
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAICompatibleSpeechProvider(api_key="x", base_url="http://example.com/v1")


def test_speech_provider_rejects_empty_unsupported_and_oversized_text():
    provider = OpenAICompatibleSpeechProvider(api_key="x")
    with pytest.raises(ValueError, match="empty or exceeds"):
        provider.synthesize("  ", "en")
    with pytest.raises(ValueError, match="input limit"):
        provider.synthesize("x" * (provider.MAX_INPUT_CHARS + 1), "en")
    with pytest.raises(ValueError, match="language"):
        provider.synthesize("hello", "fr")


def test_speech_provider_sanitizes_network_errors(monkeypatch):
    def failed_request(*_args, **_kwargs):
        raise requests.ConnectionError("test-secret leaked")

    monkeypatch.setattr(requests, "post", failed_request)
    with pytest.raises(RuntimeError) as error:
        OpenAICompatibleSpeechProvider(api_key="test-secret").synthesize("hello", "en")
    assert "test-secret" not in str(error.value)


def test_speech_provider_rejects_invalid_empty_and_oversized_audio(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse([b""]))
    with pytest.raises(ValueError, match="empty audio"):
        OpenAICompatibleSpeechProvider(api_key="x").synthesize("hello", "en")

    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse([b"not-mp3"]))
    with pytest.raises(ValueError, match="valid MP3"):
        OpenAICompatibleSpeechProvider(api_key="x").synthesize("hello", "en")

    provider = OpenAICompatibleSpeechProvider(api_key="x")
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse([b"ID3", b"x" * provider.MAX_AUDIO_BYTES]))
    with pytest.raises(ValueError, match="audio size limit"):
        provider.synthesize("hello", "en")
