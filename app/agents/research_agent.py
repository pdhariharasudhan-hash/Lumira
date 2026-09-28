from app.agents.base_agent import (
    BaseAgent
)


class ResearchAgent(
    BaseAgent
):

    def __init__(
        self
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

    def execute(
        self,
        task: str
    ):
        return {
            "success": False,
            "status": "unavailable",
            "code": "provider_unavailable",
            "message": "Research requires a configured search or research provider.",
            "task": task,
        }
