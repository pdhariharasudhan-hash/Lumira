from app.agents.base_agent import (
    BaseAgent
)

from app.core.lumira_core import (
    LumiraCore
)


class PlannerAgent(
    BaseAgent
):

    def __init__(
        self
    ):

        super().__init__(

            name=
            "planner_agent",

            description=
            "Creates plans for goals",

            capabilities=[
                "planning"
            ]
        )

        self.core = (
            LumiraCore()
        )

    def execute(
        self,
        task: str
    ):

        result = (
            self.core.plan(
                task
            )
        )

        return result