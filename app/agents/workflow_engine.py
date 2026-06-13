from app.agents.planner_agent import (
    PlannerAgent
)

from app.agents.code_agent import (
    CodeAgent
)


class WorkflowEngine:

    def __init__(
        self
    ):

        self.planner = (
            PlannerAgent()
        )

        self.code = (
            CodeAgent()
        )

    def execute(
        self,
        goal: str
    ):

        plan = (
            self.planner.execute(
                goal
            )
        )

        code_result = (
            self.code.execute(
                goal
            )
        )

        return {

            "success":
            True,

            "goal":
            goal,

            "plan":
            plan,

            "result":
            code_result
        }