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

        if not plan.get(
            "success",
            False
        ):

            return {

                "success":
                False,

                "message":
                "planning failed",

                "plan":
                plan
            }

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

            if (
                isinstance(
                    result,
                    dict
                )
                and
                result.get(
                    "success"
                ) is False
            ):

                return {

                    "success":
                    False,

                    "goal":
                    goal,

                    "failed_step":
                    step,

                    "failure":
                    result,

                    "plan":
                    plan,

                    "results":
                    results,

                    "context":
                    context
                }

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