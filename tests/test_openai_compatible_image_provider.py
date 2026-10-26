import base64
import json

import pytest
import requests

from app.services.providers.openai_compatible_image_provider import OpenAICompatibleImageProvider


class FakeResponse:
    def __init__(self, payload_chunks):
        self.payload_chunks = payload_chunks
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        assert chunk_size == 64 * 1024
        yield from self.payload_chunks

    def close(self):
        self.closed = True


def test_image_provider_posts_prompt_and_returns_validated_png(monkeypatch):
    image_bytes = b"\x89PNG\r\n\x1a\nexample-image"
    payload = json.dumps({"data": [{"b64_json": base64.b64encode(image_bytes).decode("ascii")}]})
    response = FakeResponse([payload[:20].encode(), payload[20:].encode()])
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response

    monkeypatch.setattr(requests, "post", fake_post)
    provider = OpenAICompatibleImageProvider(api_key="test-secret", timeout=999)
    result = provider.generate("Draw a clean circuit diagram", "schematic")

    assert result == {"success": True, "content": image_bytes, "extension": "png"}
    assert captured["url"] == "https://api.openai.com/v1/images/generations"
    assert captured["headers"]["Authorization"] == "Bearer test-secret"
    assert captured["json"] == {"model": "gpt-image-1", "prompt": "Draw a clean circuit diagram", "size": "1024x1024", "n": 1}
    assert captured["timeout"] == 120
    assert captured["stream"] is True
    assert response.closed is True


def test_image_provider_requires_key_and_secure_url():
    with pytest.raises(RuntimeError, match="API key"):
        OpenAICompatibleImageProvider(api_key="").generate("diagram", "diagram")
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAICompatibleImageProvider(api_key="x", base_url="http://example.com/v1")


def test_image_provider_rejects_empty_or_oversized_prompts_and_unknown_types():
    provider = OpenAICompatibleImageProvider(api_key="x")
    with pytest.raises(ValueError, match="empty or exceeds"):
        provider.generate("  ", "image")
    with pytest.raises(ValueError, match="input limit"):
        provider.generate("x" * (provider.MAX_PROMPT_CHARS + 1), "image")
    with pytest.raises(ValueError, match="not supported"):
        provider.generate("draw this", "video")


def test_image_provider_sanitizes_network_errors(monkeypatch):
    def failed_request(*_args, **_kwargs):
        raise requests.ConnectionError("test-secret leaked")

    monkeypatch.setattr(requests, "post", failed_request)
    with pytest.raises(RuntimeError) as error:
        OpenAICompatibleImageProvider(api_key="test-secret").generate("diagram", "diagram")
    assert "test-secret" not in str(error.value)


def test_image_provider_rejects_invalid_response_and_oversized_content(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse([b"not json"]))
    with pytest.raises(ValueError, match="invalid or empty"):
        OpenAICompatibleImageProvider(api_key="x").generate("diagram", "diagram")

    payload = json.dumps({"data": [{"b64_json": base64.b64encode(b"not-image").decode("ascii")}]})
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse([payload.encode()]))
    with pytest.raises(ValueError, match="supported image format"):
        OpenAICompatibleImageProvider(api_key="x").generate("diagram", "diagram")

    provider = OpenAICompatibleImageProvider(api_key="x")
    oversized = json.dumps({"data": [{"b64_json": base64.b64encode(b"x" * (provider.MAX_IMAGE_BYTES + 1)).decode("ascii")}]})
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse([oversized.encode()]))
    with pytest.raises(ValueError, match="image size limit"):
        provider.generate("diagram", "diagram")
