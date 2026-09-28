from app.services.research.research_capability_service import ResearchCapabilityService


def test_external_research_reports_missing_provider_without_fabricating_findings():
    result = ResearchCapabilityService().web_research("current battery technology")
    assert result["success"] is False
    assert result["status"] == "unavailable"
    assert result["code"] == "provider_unavailable"
    assert "findings" not in result


def test_local_knowledge_retrieval_uses_unified_search_results():
    service = ResearchCapabilityService()
    service.search.search_all = lambda query: {"projects": [{"project_id": "p1", "query": query}], "artifacts": []}
    result = service.knowledge_retrieval("expense API")
    assert result["success"] is True
    assert result["source"] == "lumira_local_search"
    assert result["result_count"] == 1
    assert result["results"]["projects"][0]["project_id"] == "p1"


def test_research_provider_exceptions_and_unsubstantiated_success_are_rejected():
    class RaisingProvider:
        def research(self, request, research_type):
            raise RuntimeError("secret provider details")

    class EmptyProvider:
        def research(self, request, research_type):
            return {"success": True, "sources": [{"url": "https://example.test"}]}

    class NoSourcesProvider:
        def research(self, request, research_type):
            return {"success": True, "findings": "A finding without evidence."}

    failed = ResearchCapabilityService(RaisingProvider()).web_research("question")
    assert failed["code"] == "provider_error"
    assert "secret provider details" not in str(failed)
    assert "findings" not in failed

    empty = ResearchCapabilityService(EmptyProvider()).web_research("question")
    assert empty["code"] == "invalid_provider_response"
    assert "findings" not in empty

    unsupported = ResearchCapabilityService(NoSourcesProvider()).web_research("question")
    assert unsupported["code"] == "invalid_provider_response"
    assert "findings" not in unsupported


def test_research_provider_success_is_normalized_to_bounded_findings_and_sources():
    class Provider:
        def research(self, request, research_type):
            return {
                "success": True,
                "findings": ["Verified finding."],
                "sources": [{"url": "https://example.test/source"}],
                "provider_secret": "must not escape",
            }

    result = ResearchCapabilityService(Provider()).web_research("question")
    assert result["success"] is True
    assert result["findings"] == ["Verified finding."]
    assert result["sources"] == [{"url": "https://example.test/source"}]
    assert "provider_secret" not in result
