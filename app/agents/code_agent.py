from app.agents.base_agent import (
    BaseAgent
)

from app.core.lumira_core import (
    LumiraCore
)


class CodeAgent(
    BaseAgent
):

    def __init__(
        self
    ):

        super().__init__(

            name=
            "code_agent",

            description=
            "Generates code projects",

            capabilities=[
                "code_generation"
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
            self.core.generate(
                task
            )
        )

        return result