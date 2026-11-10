import json

import pytest

from app.services.providers.ollama_summary_provider import OllamaSummaryProvider
from app.services.resources.resource_budget_service import ResourceBudgetService


@pytest.fixture(autouse=True)
def deterministic_resource_budget(monkeypatch):
    # These tests validate provider contracts; memory-pressure policy is
    # covered independently and must not make network mocks nondeterministic.
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_profile": "low_memory",
            "resource_pressure": "normal",
            "max_concurrent_agents": 1,
            "max_concurrent_local_model_requests": 1,
            "max_provider_files": 6,
            "max_context_characters": 30000,
            "max_file_characters": 12000,
            "avoid_loading_multiple_local_models": True,
            "defer_optional_heavy_media_work": False,
        },
    )


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit=-1):
        return self.payload if limit < 0 else self.payload[:limit]


def test_ollama_summary_provider_uses_bounded_openai_compatible_request(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"choices": [{"message": {"content": "Main points: வணக்கம்; create a report."}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaSummaryProvider(timeout=200)
    result = provider.summarize("வணக்கம் Lumira, create a report")

    assert result == "Main points: வணக்கம்; create a report."
    assert captured["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert captured["timeout"] == 120
    assert captured["payload"]["model"] == "qwen2.5-coder:3b"
    assert captured["payload"]["temperature"] == 0
    assert captured["payload"]["stream"] is False


def test_ollama_summary_provider_rejects_empty_or_oversized_transcript():
    provider = OllamaSummaryProvider()
    with pytest.raises(ValueError, match="empty"):
        provider.summarize("  ")
    with pytest.raises(ValueError, match="input limit"):
        provider.summarize("x" * (provider.MAX_INPUT_CHARS + 1))


def test_ollama_summary_provider_rejects_invalid_provider_output(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse({"choices": []}))
    with pytest.raises(ValueError, match="empty summary"):
        OllamaSummaryProvider().summarize("A short transcript.")


@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.com/v1",
        "http://192.168.1.20:11434/v1",
        "http://user:secret@127.0.0.1:11434/v1",
        "http://127.0.0.1:99999/v1",
        "http://127.0.0.1:11434/v1?token=secret",
    ],
)
def test_ollama_summary_provider_rejects_nonlocal_or_unsafe_endpoints(base_url):
    with pytest.raises(ValueError, match="local"):
        OllamaSummaryProvider(base_url=base_url)
