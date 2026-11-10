from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import requests


class TavilyResearchProvider:

    """Opt-in, source-backed web research using the Tavily search API."""

    provider_scope = "external"
    ENDPOINT = "https://api.tavily.com/search"
    MAX_QUERY_CHARS = 4_000
    MAX_RESPONSE_BYTES = 5_000_000
    MAX_RESULTS = 10
    MAX_FINDING_CHARS = 10_000
    MAX_TOTAL_FINDINGS_CHARS = 100_000

    def __init__(self, *, api_key: str | None = None, timeout: int = 30, max_results: int = 6) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("LUMIRA_RESEARCH_API_KEY", "")
        self.timeout = max(5, min(int(timeout), 60))
        self.max_results = max(1, min(int(max_results), self.MAX_RESULTS))
        parsed = urlparse(self.ENDPOINT)
        if parsed.scheme != "https" or parsed.hostname != "api.tavily.com":
            raise ValueError("Research endpoint must use the trusted HTTPS endpoint.")

    def research(self, request: str, research_type: str) -> dict:
        if not self.api_key.strip():
            raise RuntimeError("Research API key is not configured.")
        if not isinstance(request, str) or not request.strip() or len(request) > self.MAX_QUERY_CHARS:
            raise ValueError("Research query is empty or exceeds the query limit.")
        if not isinstance(research_type, str) or not research_type.strip() or len(research_type) > 80:
            raise ValueError("Research type is invalid.")

        response = None
        try:
            response = requests.post(
                self.ENDPOINT,
                headers={"Content-Type": "application/json"},
                json={
                    "api_key": self.api_key,
                    "query": request.strip(),
                    "search_depth": "basic",
                    "topic": "general",
                    "max_results": self.max_results,
                    "include_answer": True,
                    "include_raw_content": False,
                },
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.MAX_RESPONSE_BYTES:
                    raise ValueError("Research response exceeds the response size limit.")
                chunks.append(chunk)
        except requests.RequestException:
            raise RuntimeError("Research service request failed; check connectivity and provider configuration.") from None
        finally:
            if response is not None:
                response.close()

        try:
            payload = json.loads(b"".join(chunks).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("Research service returned an invalid response.") from None

        if not isinstance(payload, dict):
            raise ValueError("Research service response must be an object.")
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise ValueError("Research service response contains no result list.")

        findings: list[str] = []
        sources: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        answer = payload.get("answer")
        if isinstance(answer, str) and answer.strip():
            answer = answer.strip()[:self.MAX_FINDING_CHARS]
            findings.append("Provider synthesis (verify against cited sources): " + answer)

        for item in raw_results[:self.max_results]:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            title = item.get("title")
            content = item.get("content")
            if not isinstance(url, str) or not url.startswith("https://") or len(url) > 2_048 or url in seen_urls:
                continue
            parsed_url = urlparse(url)
            if not parsed_url.hostname or parsed_url.username or parsed_url.password:
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            seen_urls.add(url)
            safe_title = title.strip()[:500] if isinstance(title, str) and title.strip() else url
            prefix = f"{safe_title}: "
            remaining = self.MAX_TOTAL_FINDINGS_CHARS - sum(len(finding) for finding in findings)
            if remaining <= len(prefix):
                break
            raw_content = content.strip()
            safe_content = raw_content[:min(self.MAX_FINDING_CHARS, remaining - len(prefix))]
            if not safe_content:
                continue
            sources.append({"title": safe_title, "url": url, "published_date": str(item.get("published_date") or "")[:40]})
            findings.append(prefix + safe_content)
            if len(safe_content) < len(raw_content):
                break

        if not findings or not sources:
            raise ValueError("Research service returned no usable findings with source URLs.")
        return {"success": True, "findings": findings, "sources": sources, "research_type": research_type}
