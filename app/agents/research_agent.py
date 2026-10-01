from app.agents.base_agent import (
    BaseAgent
)
from app.services.research.research_capability_service import (
    ResearchCapabilityService,
)


class ResearchAgent(
    BaseAgent
):

    def __init__(
        self,
        research: ResearchCapabilityService | None = None,
    ):

        super().__init__(

            name=
            "research_agent",

            description=
            "Research tasks",

            capabilities=[
                "research"
            ]
        )

        self.research = research or ResearchCapabilityService()

    def execute(
        self,
        task: str
    ):
        task_lower = task.casefold()
        if any(term in task_lower for term in ("local", "document", "workspace", "memory")):
            result = self.research.knowledge_retrieval(task)
        else:
            result = self.research.web_research(task)

        return {
            **result,
            "task": task,
        }
