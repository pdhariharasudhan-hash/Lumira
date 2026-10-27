import json

import pytest

from app.services.providers.ollama_summary_provider import OllamaSummaryProvider


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



def test_summary_defers_when_memory_pressure_is_critical(monkeypatch):
    from app.services.resources.resource_budget_service import ResourceBudgetService

    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "max_context_characters": 40000,
            "resource_pressure": "critical",
            "resource_profile": "balanced",
        },
    )
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("network must not be called under critical memory pressure")
        ),
    )
    with pytest.raises(RuntimeError, match="memory pressure is critical"):
        OllamaSummaryProvider().summarize("A short transcript.")


def test_summary_uses_smaller_token_budget_for_low_memory_profile(monkeypatch):
    from app.services.resources.resource_budget_service import ResourceBudgetService

    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"choices": [{"message": {"content": "Short summary."}}]})

    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "max_context_characters": 40000,
            "resource_pressure": "normal",
            "resource_profile": "low_memory",
        },
    )
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert OllamaSummaryProvider().summarize("A short transcript.") == "Short summary."
    assert captured["payload"]["max_tokens"] == 1024


def test_summary_rejects_oversized_response_and_sanitizes_network_error(monkeypatch):
    import urllib.error

    def oversized(*_args, **_kwargs):
        return FakeResponse({"choices": [{"message": {"content": "x" * (OllamaSummaryProvider.MAX_OUTPUT_CHARS + 1)}}]})

    monkeypatch.setattr("urllib.request.urlopen", oversized)
    with pytest.raises(ValueError, match="response limit"):
        OllamaSummaryProvider().summarize("A short transcript.")

    def unavailable(*_args, **_kwargs):
        raise urllib.error.URLError("private endpoint details")

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    with pytest.raises(RuntimeError, match="endpoint is unavailable") as exc:
        OllamaSummaryProvider().summarize("A short transcript.")
    assert "private endpoint details" not in str(exc.value)
