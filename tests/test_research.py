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


def test_local_retrieval_bounds_results_and_nested_content():
    service = ResearchCapabilityService()
    service.search.search_all = lambda query: {
        "projects": [{"content": "x" * 9000, "nested": {"items": list(range(30))}} for _ in range(25)],
        "artifacts": [{"artifact_id": str(index)} for index in range(150)],
        "invalid_category": "ignored",
    }

    result = service.knowledge_retrieval("  bounded query  ")

    assert result["success"] is True
    assert result["request"] == "bounded query"
    assert result["result_count"] == 40
    assert len(result["results"]["projects"]) == 20
    assert len(result["results"]["projects"][0]["content"]) == 4000
    assert len(result["results"]["projects"][0]["nested"]["items"]) == 20
    assert len(result["results"]["artifacts"]) == 20


def test_local_retrieval_handles_search_exceptions_without_leaking_details():
    service = ResearchCapabilityService()
    service.search.search_all = lambda query: (_ for _ in ()).throw(RuntimeError("private path / secret"))
    result = service.knowledge_retrieval("find my note")
    assert result["success"] is False
    assert result["code"] == "local_search_failed"
    assert "private path" not in str(result)


def test_local_retrieval_rejects_invalid_search_result_shape():
    service = ResearchCapabilityService()
    service.search.search_all = lambda query: ["not", "an", "object"]
    result = service.document_research("find document")
    assert result["success"] is False
    assert result["code"] == "invalid_local_search_result"


def test_research_agent_selects_specialized_existing_capabilities():
    from app.agents.research_agent import ResearchAgent

    expected = {
        "compare two local projects": "comparison",
        "market research on local schools": "market_research",
        "technical research on a battery": "technical_research",
        "document research in my workspace": "document_research",
        "gather evidence for the proposal": "evidence_gathering",
        "summarize research findings": "research_summaries",
        "extract knowledge from these notes": "knowledge_extraction",
        "search my memory for this decision": "knowledge_retrieval",
        "research current solar technology": "web_research",
    }
    for task, route in expected.items():
        assert ResearchAgent._select_route(task) == route


def test_research_agent_rejects_empty_task_and_invalid_capability_result():
    from app.agents.research_agent import ResearchAgent

    agent = ResearchAgent(research=object())
    empty = agent.execute("   ")
    assert empty["code"] == "invalid_research_request"

    class InvalidResearch:
        def web_research(self, request):
            return ["invalid"]

    invalid = ResearchAgent(research=InvalidResearch()).execute("research current topic")
    assert invalid["code"] == "invalid_research_result"



def test_external_research_rejects_empty_and_oversized_requests_before_provider_call():
    class MustNotRunProvider:
        def research(self, request, research_type):
            raise AssertionError("provider should not receive invalid requests")

    service = ResearchCapabilityService(MustNotRunProvider())
    assert service.web_research(" ")["code"] == "invalid_research_request"
    assert service.technical_research("x" * 10_001)["code"] == "invalid_research_request"


def test_validated_external_research_is_bridged_into_research_library():
    class Provider:
        def research(self, request, research_type):
            return {
                "success": True,
                "findings": ["Supported finding."],
                "sources": [{"url": "https://example.test/evidence"}],
            }

    class Library:
        def __init__(self):
            self.calls = []
        def add(self, **kwargs):
            self.calls.append(kwargs)
            return {"research_id": "research-1"}

    library = Library()
    result = ResearchCapabilityService(Provider(), library=library).web_research("battery research")
    assert result["success"] is True
    assert result["storage_status"] == "stored"
    assert result["research_id"] == "research-1"
    assert library.calls[0]["source"] == "https://example.test/evidence"
    assert library.calls[0]["tags"] == ["web_research"]


def test_research_storage_failure_does_not_fake_a_saved_record():
    class Provider:
        def research(self, request, research_type):
            return {
                "success": True,
                "findings": "Supported finding.",
                "sources": [{"source": "source-1"}],
            }

    class BrokenLibrary:
        def add(self, **kwargs):
            raise OSError("storage unavailable")

    result = ResearchCapabilityService(Provider(), library=BrokenLibrary()).technical_research("battery")
    assert result["success"] is True
    assert result["storage_status"] == "failed"
    assert "research_id" not in result
