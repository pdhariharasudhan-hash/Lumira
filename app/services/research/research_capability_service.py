from typing import Any, Protocol

from app.services.search.unified_search_service import UnifiedSearchService
from app.services.research.research_library_service import ResearchLibraryService



from app.services.providers.provider_access_policy_service import ProviderAccessDenied, ProviderAccessPolicyService

class ResearchProvider(Protocol):
    def research(self, request: str, research_type: str) -> dict[str, Any]:
        """Return findings with supporting source references."""


class ResearchCapabilityService:
    """Provider-backed research plus retrieval from Lumira's local index."""

    def __init__(self, provider: ResearchProvider | None = None, library: ResearchLibraryService | None = None, *, provider_policy=None):
        if provider is None:
            from app.services.providers.provider_registry import ProviderRegistry

            provider = ProviderRegistry.get("research")
        self.provider = provider
        self.provider_policy = provider_policy or ProviderAccessPolicyService()
        self.search = UnifiedSearchService()
        self.library = library or ResearchLibraryService()

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
            self.provider_policy.authorize(self.provider, "web research")
            response = self.provider.research(request, research_type)
        except ProviderAccessDenied as error:
            return {"success": False, "status": "blocked", "code": error.code, "research_type": research_type, "message": error.user_message}
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
        result = {
            "success": True,
            "status": "completed",
            "research_type": research_type,
            "findings": findings,
            "sources": sources,
        }
        # Accepted external research is kept in Lumira's research library so it
        # becomes searchable later. Provider output is never written to durable
        # memory unless it passed the findings/source validation above.
        try:
            primary_source = next(
                (
                    str(item.get("url") or item.get("source")).strip()
                    for item in sources
                    if isinstance(item, dict) and str(item.get("url") or item.get("source") or "").strip()
                ),
                "",
            )
            summary = findings if isinstance(findings, str) else "\n".join(findings)
            saved = self.library.add(
                title=request[:300],
                source=primary_source,
                summary=summary,
                tags=[research_type],
            )
            research_id = saved.get("research_id") if isinstance(saved, dict) else None
            if isinstance(research_id, str) and research_id:
                result["research_id"] = research_id
                result["storage_status"] = "stored"
            else:
                result["storage_status"] = "failed"
        except Exception:
            # Research itself remains usable when optional library persistence
            # fails; never claim a durable record was created.
            result["storage_status"] = "failed"
        try:
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService
            import json
            artifact = ArtifactManagerService().create_artifact(
                artifact_type="reports",
                content=json.dumps({
                    "request": request,
                    "research_type": research_type,
                    "findings": findings,
                    "sources": sources,
                    "research_id": result.get("research_id"),
                }, ensure_ascii=False),
                source=f"research:{research_type}",
                extension="json",
            )
            if isinstance(artifact, dict) and isinstance(artifact.get("artifact_id"), str):
                result["artifact_id"] = artifact["artifact_id"]
                result["artifact_storage"] = "stored"
            else:
                result["artifact_storage"] = "failed"
        except (OSError, TypeError, ValueError):
            result["artifact_storage"] = "failed"
        return result

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
