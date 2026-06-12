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

            "research":
            f"Research completed for: {task}"
        }