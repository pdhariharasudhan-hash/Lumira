from __future__ import annotations

import base64
import json

import pytest

from app.services.providers.ollama_vision_provider import OllamaVisionProvider


PNG = b"\x89PNG\r\n\x1a\n" + b"test-image"


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body
        self.read_limit = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit: int = -1) -> bytes:
        self.read_limit = limit
        return self.body[:limit]


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return self.response


def test_ollama_vision_requires_loopback_http_without_credentials():
    for url in (
        "https://example.com",
        "http://example.com:11434",
        "http://user:password@127.0.0.1:11434",
        "http://127.0.0.1:11434?forward=1",
    ):
        with pytest.raises(ValueError):
            OllamaVisionProvider(base_url=url)


def test_ollama_vision_sends_image_to_local_api_and_bounds_response(monkeypatch):
    body = json.dumps(
        {"message": {"content": "A small test image."}}
    ).encode("utf-8")
    response = FakeResponse(body)
    opener = FakeOpener(response)
    proxy_handler_called = []
    build_opener_called = []

    class FakeProxyHandler:
        def __init__(self, proxies):
            proxy_handler_called.append(proxies)

    def fake_build_opener(handler):
        build_opener_called.append(handler)
        return opener

    monkeypatch.setattr(
        "app.services.providers.ollama_vision_provider.urllib.request.ProxyHandler",
        FakeProxyHandler,
    )
    monkeypatch.setattr(
        "app.services.providers.ollama_vision_provider.urllib.request.build_opener",
        fake_build_opener,
    )

    result = OllamaVisionProvider(model="moondream").analyze(
        PNG, "Read the visible text."
    )

    assert result == {"success": True, "description": "A small test image.", "model": "moondream"}
    assert proxy_handler_called == [{}]
    assert len(build_opener_called) == 1
    assert opener.timeout == 90
    assert response.read_limit == OllamaVisionProvider.MAX_RESPONSE_BYTES + 1
    request_payload = json.loads(opener.request.data.decode("utf-8"))
    assert request_payload["model"] == "moondream"
    assert request_payload["stream"] is False
    assert request_payload["messages"][1]["content"] == "Read the visible text."
    assert request_payload["messages"][1]["images"] == [base64.b64encode(PNG).decode("ascii")]


def test_ollama_vision_rejects_invalid_image_and_prompt_before_network(monkeypatch):
    def no_network(*_args, **_kwargs):
        raise AssertionError("network must not be called for invalid input")

    monkeypatch.setattr(
        "app.services.providers.ollama_vision_provider.urllib.request.build_opener",
        no_network,
    )
    provider = OllamaVisionProvider()

    with pytest.raises(ValueError, match="valid PNG"):
        provider.analyze(b"not-an-image")
    with pytest.raises(ValueError, match="prompt"):
        provider.analyze(PNG, " ")


def test_ollama_vision_rejects_oversized_response(monkeypatch):
    response = FakeResponse(b"x" * (OllamaVisionProvider.MAX_RESPONSE_BYTES + 1))
    opener = FakeOpener(response)
    monkeypatch.setattr(
        "app.services.providers.ollama_vision_provider.urllib.request.build_opener",
        lambda _handler: opener,
    )

    with pytest.raises(ValueError, match="response exceeds"):
        OllamaVisionProvider().analyze(PNG)


def test_ollama_vision_rejects_malformed_or_empty_model_output(monkeypatch):
    for body in (b"not-json", b'{"message":{"content":"   "}}'):
        response = FakeResponse(body)
        opener = FakeOpener(response)
        monkeypatch.setattr(
            "app.services.providers.ollama_vision_provider.urllib.request.build_opener",
            lambda _handler, opener=opener: opener,
        )
        with pytest.raises(ValueError):
            OllamaVisionProvider().analyze(PNG)
