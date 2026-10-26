from typing import Any, Protocol

from app.services.search.unified_search_service import UnifiedSearchService


class ResearchProvider(Protocol):
    def research(self, request: str, research_type: str) -> dict[str, Any]:
        """Return findings with supporting source references."""


class ResearchCapabilityService:
    """Provider-backed research plus retrieval from Lumira's local index."""

    def __init__(self, provider: ResearchProvider | None = None):
        if provider is None:
            from app.services.providers.provider_registry import ProviderRegistry

            provider = ProviderRegistry.get("research")
        self.provider = provider
        self.search = UnifiedSearchService()

    def _provider_research(self, request: str, research_type: str) -> dict[str, Any]:
        if not isinstance(request, str) or not request.strip() or len(request) > 10_000:
            return {
                "success": False,
                "status": "rejected",
                "code": "invalid_research_request",
                "research_type": research_type,
                "message": "Research requests must contain 1 to 10000 characters.",
            }
        request = request.strip()
        if self.provider is None:
            return {
                "success": False,
                "status": "unavailable",
                "code": "provider_unavailable",
                "research_type": research_type,
                "message": "No external research provider is configured; no findings were generated.",
            }
        try:
            response = self.provider.research(request, research_type)
        except Exception:
            return {
                "success": False,
                "status": "failed",
                "code": "provider_error",
                "research_type": research_type,
                "message": "The research provider failed; no findings were accepted.",
            }
        sources = response.get("sources") if isinstance(response, dict) else None
        findings = response.get("findings") if isinstance(response, dict) else None
        if isinstance(findings, str):
            valid_findings = bool(findings.strip()) and len(findings) <= 100_000
        elif isinstance(findings, list):
            valid_findings = (
                1 <= len(findings) <= 100
                and all(isinstance(item, str) and item.strip() and len(item) <= 10_000 for item in findings)
                and sum(len(item) for item in findings) <= 100_000
            )
        else:
            valid_findings = False
        valid_sources = (
            isinstance(sources, list)
            and 1 <= len(sources) <= 100
            and all(
                isinstance(source, dict)
                and isinstance(source.get("url") or source.get("source"), str)
                and bool((source.get("url") or source.get("source")).strip())
                and len(source.get("url") or source.get("source")) <= 2_048
                for source in sources
            )
        )
        if (
            not isinstance(response, dict)
            or response.get("success") is not True
            or not valid_findings
            or not valid_sources
        ):
            return {
                "success": False,
                "status": "failed",
                "code": "invalid_provider_response",
                "research_type": research_type,
                "message": "The research provider must return bounded findings with source references.",
            }
        return {
            "success": True,
            "status": "completed",
            "research_type": research_type,
            "findings": findings,
            "sources": sources,
        }

    @classmethod
    def _bound_local_value(cls, value: Any, *, depth: int = 0) -> Any:
        """Bound indexed content before returning it through an agent response."""
        if depth >= 5:
            return "[nested content omitted]"
        if isinstance(value, str):
            return value[:4_000]
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [cls._bound_local_value(item, depth=depth + 1) for item in value[:20]]
        if isinstance(value, dict):
            return {
                str(key)[:100]: cls._bound_local_value(item, depth=depth + 1)
                for key, item in list(value.items())[:30]
                if isinstance(key, (str, int, float))
            }
        return str(type(value).__name__)

    def _local_retrieval(self, request: str, research_type: str) -> dict[str, Any]:
        if not isinstance(request, str) or not request.strip():
            return {
                "success": False,
                "status": "rejected",
                "code": "invalid_research_request",
                "research_type": research_type,
                "message": "Research request must be non-empty text.",
            }
        try:
            raw_results = self.search.search_all(request.strip()[:10_000])
        except Exception:
            return {
                "success": False,
                "status": "failed",
                "code": "local_search_failed",
                "research_type": research_type,
                "message": "Local search failed; no results were accepted.",
            }
        if not isinstance(raw_results, dict):
            return {
                "success": False,
                "status": "failed",
                "code": "invalid_local_search_result",
                "research_type": research_type,
                "message": "Local search returned an invalid result.",
            }
        results = {}
        remaining = 100
        for key, items in raw_results.items():
            if remaining <= 0:
                break
            if not isinstance(key, str) or not isinstance(items, list):
                continue
            selected = items[:min(20, remaining)]
            results[key[:100]] = self._bound_local_value(selected)
            remaining -= len(selected)
        return {
            "success": True,
            "status": "completed",
            "research_type": research_type,
            "request": request.strip()[:10_000],
            "source": "lumira_local_search",
            "results": results,
            "result_count": sum(len(items) for items in results.values() if isinstance(items, list)),
            "limits": {"max_total_results": 100, "max_results_per_category": 20, "max_result_string_length": 4000},
        }

    def web_research(self, request: str) -> dict[str, Any]:
        return self._provider_research(request, "web_research")

    def document_research(self, request: str) -> dict[str, Any]:
        return self._local_retrieval(request, "document_research")

    def knowledge_retrieval(self, request: str) -> dict[str, Any]:
        return self._local_retrieval(request, "knowledge_retrieval")

    def technical_research(self, request: str) -> dict[str, Any]:
        return self._provider_research(request, "technical_research")

    def market_research(self, request: str) -> dict[str, Any]:
        return self._provider_research(request, "market_research")

    def comparison(self, request: str) -> dict[str, Any]:
        return self._provider_research(request, "comparison")

    def evidence_gathering(self, request: str) -> dict[str, Any]:
        return self._provider_research(request, "evidence_gathering")

    def research_summaries(self, request: str) -> dict[str, Any]:
        return self._provider_research(request, "research_summaries")

    def knowledge_extraction(self, request: str) -> dict[str, Any]:
        return self._provider_research(request, "knowledge_extraction")
