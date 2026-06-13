from app.core.lumira_core import (
    LumiraCore
)

from app.agents.code_agent import (
    CodeAgent
)


class WorkflowStepRouter:

    def __init__(
        self
    ):

        self.core = (
            LumiraCore()
        )

        self.code_agent = (
            CodeAgent()
        )

    def execute_step(
        self,
        step: str,
        goal: str
    ):

        if step == "validate":

            return {

                "step":
                step,

                "status":
                "completed"
            }

        if step == "builder":

            return (
                self.core.build(
                    goal
                )
            )

        if step == "execute":

            return (
                self.core.execute(
                    goal
                )
            )

        if step == "code":

            return (
                self.code_agent.execute(
                    goal
                )
            )

        if step == "save_project":

            return {

                "step":
                step,

                "status":
                "pending"
            }

        return {

            "step":
            step,

            "status":
            "unknown"
        }