from app.agents.base_agent import BaseAgent
from app.services.research.research_capability_service import ResearchCapabilityService


class ResearchAgent(BaseAgent):
    """Route research requests to the matching bounded local or provider capability."""

    _ROUTES = (
        (("knowledge extraction", "extract knowledge", "extract facts"), "knowledge_extraction"),
        (("evidence gathering", "gather evidence", "evidence for"), "evidence_gathering"),
        (("research summary", "summarize research", "summarise research"), "research_summaries"),
        (("compare", "comparison", "versus", " vs "), "comparison"),
        (("market research", "market analysis", "industry research"), "market_research"),
        (("technical research", "technical investigation", "engineering research"), "technical_research"),
        (("document research", "search documents", "find in documents"), "document_research"),
        (("local", "document", "workspace", "memory", "knowledge base", "saved files"), "knowledge_retrieval"),
    )

    def __init__(self, research: ResearchCapabilityService | None = None):
        super().__init__(
            name="research_agent",
            description="Research tasks across local knowledge and configured research providers",
            capabilities=[
                "research",
                "web_research",
                "document_research",
                "knowledge_retrieval",
                "technical_research",
                "market_research",
                "comparison",
                "evidence_gathering",
                "research_summaries",
                "knowledge_extraction",
            ],
        )
        self.research = research or ResearchCapabilityService()

    @staticmethod
    def _select_route(task: str) -> str:
        normalized = " " + " ".join(task.casefold().split()) + " "
        for phrases, route in ResearchAgent._ROUTES:
            if any(phrase in normalized for phrase in phrases):
                return route
        return "web_research"

    def execute(self, task: str):
        if not isinstance(task, str) or not task.strip():
            return {
                "success": False,
                "status": "rejected",
                "code": "invalid_research_request",
                "message": "Research task must be non-empty text.",
            }

        route = self._select_route(task)
        capability = getattr(self.research, route, None)
        if not callable(capability):
            return {
                "success": False,
                "status": "unavailable",
                "code": "research_capability_unavailable",
                "research_type": route,
                "message": "The selected research capability is not available.",
                "task": task.strip()[:10000],
            }

        result = capability(task.strip()[:10000])
        if not isinstance(result, dict):
            return {
                "success": False,
                "status": "failed",
                "code": "invalid_research_result",
                "research_type": route,
                "message": "Research capability returned an invalid result.",
            }
        return {
            **result,
            "research_type": result.get("research_type", route),
            "task": task.strip()[:10000],
        }
