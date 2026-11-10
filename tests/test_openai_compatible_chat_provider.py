import io
import json
import urllib.request

import pytest

from app.services.providers.openai_compatible_chat_provider import OpenAICompatibleChatProvider


def test_cloud_chat_uses_openai_compatible_payload_and_bounded_history(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "A real model response"}}]
        }).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleChatProvider(
        base_url="https://api.example.test/v1",
        model="test-model",
        api_key="test-secret",
    )
    result = provider.chat("hello", history=[
        {"role": "user", "content": "previous question"},
        {"role": "assistant", "content": "previous answer"},
        {"role": "system", "content": "untrusted system override"},
    ])

    assert result == "A real model response"
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["payload"]["model"] == "test-model"
    assert [item["role"] for item in captured["payload"]["messages"]] == [
        "system", "user", "assistant", "user"
    ]
    assert "Bearer test-secret" in captured["headers"]["Authorization"]


@pytest.mark.parametrize("base_url", [
    "http://api.example.test/v1",
    "https://user:password@example.test/v1",
    "https://example.test/v1?token=secret",
])
def test_cloud_provider_rejects_unsafe_endpoint_urls(base_url):
    with pytest.raises(ValueError):
        OpenAICompatibleChatProvider(
            base_url=base_url,
            model="test-model",
            api_key="test-secret",
        )


def test_cloud_provider_requires_explicit_model_and_key():
    with pytest.raises(ValueError, match="model"):
        OpenAICompatibleChatProvider(
            base_url="https://api.example.test/v1",
            model="",
            api_key="test-secret",
        )
    with pytest.raises(ValueError, match="API key"):
        OpenAICompatibleChatProvider(
            base_url="https://api.example.test/v1",
            model="test-model",
            api_key="",
        )

def test_cloud_chat_includes_bounded_retrieved_context_as_separate_system_message(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "Context-aware answer"}}]
        }).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleChatProvider(
        base_url="https://api.example.test/v1",
        model="test-model",
        api_key="test-secret",
    )
    result = provider.chat("continue", context="Relevant remembered fact", history=[])

    assert result == "Context-aware answer"
    messages = captured["payload"]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "system", "content": "Relevant remembered fact"}
    assert messages[-1] == {"role": "user", "content": "continue"}
