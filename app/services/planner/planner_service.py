from app.services.planner.goal_decomposer import (
    GoalDecomposer
)

from app.services.planner.plan_registry import (
    PlanRegistry
)


class PlannerService:

    def __init__(self):

        self.decomposer = (
            GoalDecomposer()
        )

        self.registry = (
            PlanRegistry()
        )

    def create_plan(
        self,
        goal: str
    ):

        decomposition = (
            self.decomposer.decompose(
                goal
            )
        )

        intent = (
            decomposition[
                "intent"
            ]
        )

        steps = (
            self.registry.get_plan(
                intent
            )
        )

        return {

            "success":
            True,

            "goal":
            goal,

            "intent":
            intent,

            "steps":
            stepsaac
        }