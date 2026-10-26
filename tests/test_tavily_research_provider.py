import json

import pytest
import requests

from app.services.providers.tavily_research_provider import TavilyResearchProvider


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        assert chunk_size == 64 * 1024
        yield self.body

    def close(self):
        self.closed = True


def test_provider_sends_bounded_query_and_returns_findings_with_sources(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        response = FakeResponse({
            "answer": "Compare current battery chemistries.",
            "results": [
                {"title": "Research Paper", "url": "https://example.org/paper", "content": "A source-backed finding.", "published_date": "2026-01-01"},
                {"title": "Duplicate", "url": "https://example.org/paper", "content": "Duplicate source."},
                {"title": "Unsafe", "url": "http://example.org/page", "content": "Should be ignored."},
                {"title": "Missing text", "url": "https://example.org/empty", "content": " "},
            ],
        })
        captured["response"] = response
        return response

    monkeypatch.setattr(requests, "post", fake_post)
    result = TavilyResearchProvider(api_key="local-test-key", timeout=999, max_results=99).research("battery technology", "web_research")

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["json"]["api_key"] == "local-test-key"
    assert captured["json"]["query"] == "battery technology"
    assert captured["json"]["max_results"] == 10
    assert captured["json"]["search_depth"] == "basic"
    assert captured["timeout"] == 60
    assert captured["stream"] is True
    assert captured["response"].closed is True
    assert result["success"] is True
    assert len(result["sources"]) == 1
    assert result["sources"][0]["url"] == "https://example.org/paper"
    assert any("source-backed finding" in finding for finding in result["findings"])


def test_provider_requires_key_and_rejects_invalid_queries():
    with pytest.raises(RuntimeError, match="API key"):
        TavilyResearchProvider(api_key="").research("query", "web_research")
    provider = TavilyResearchProvider(api_key="x")
    with pytest.raises(ValueError, match="query limit"):
        provider.research("x" * (provider.MAX_QUERY_CHARS + 1), "web_research")
    with pytest.raises(ValueError, match="Research type"):
        provider.research("query", "x" * 81)


def test_provider_sanitizes_network_and_json_errors(monkeypatch):
    def failed_request(*_args, **_kwargs):
        raise requests.ConnectionError("local-test-key leaked")

    monkeypatch.setattr(requests, "post", failed_request)
    with pytest.raises(RuntimeError) as error:
        TavilyResearchProvider(api_key="local-test-key").research("query", "web_research")
    assert "local-test-key" not in str(error.value)

    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse([]))
    with pytest.raises(ValueError, match="object"):
        TavilyResearchProvider(api_key="x").research("query", "web_research")


def test_provider_rejects_no_results_and_limits_findings(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse({"results": []}))
    with pytest.raises(ValueError, match="no usable findings"):
        TavilyResearchProvider(api_key="x").research("query", "web_research")

    provider = TavilyResearchProvider(api_key="x")
    payload = {"results": [{"title": "Big", "url": "https://example.org/big", "content": "x" * (provider.MAX_FINDING_CHARS + 100)}]}
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse(payload))
    result = provider.research("query", "web_research")
    assert len(result["findings"][-1]) <= provider.MAX_FINDING_CHARS + 510

    oversized_payload = {"answer": "x" * provider.MAX_RESPONSE_BYTES, "results": []}
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse(oversized_payload))
    with pytest.raises(ValueError, match="response size limit"):
        provider.research("query", "web_research")


def test_provider_keeps_total_findings_within_service_limit(monkeypatch):
    provider = TavilyResearchProvider(api_key="x", max_results=10)
    payload = {
        "answer": "a" * provider.MAX_FINDING_CHARS,
        "results": [
            {"title": f"Source {index}", "url": f"https://example.org/{index}", "content": "x" * provider.MAX_FINDING_CHARS}
            for index in range(10)
        ],
    }
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: FakeResponse(payload))
    result = provider.research("query", "web_research")
    assert sum(map(len, result["findings"])) <= provider.MAX_TOTAL_FINDINGS_CHARS
    assert len(result["sources"]) == len(result["findings"]) - 1
