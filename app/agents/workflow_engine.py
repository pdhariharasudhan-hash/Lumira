from app.agents.planner_agent import (
    PlannerAgent
)

from app.agents.workflow_step_router import (
    WorkflowStepRouter
)


class WorkflowEngine:

    def __init__(
        self
    ):

        self.planner = (
            PlannerAgent()
        )

        self.router = (
            WorkflowStepRouter()
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

        results = []

        context = {}

        for step in plan[
            "steps"
        ]:

            result = (
                self.router.execute_step(
                    step,
                    goal,
                    context
                )
            )

            context[
                step
            ] = result

            results.append(
                result
            )

        return {

            "success":
            True,

            "goal":
            goal,

            "plan":
            plan,

            "results":
            results,

            "context":
            context
        }