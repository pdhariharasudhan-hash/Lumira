from datetime import datetime

from app.services.decision.decision_models import (
    DecisionState,
)

from app.services.reasoning.reasoning_models import (
    ReasoningState,
)

from app.services.planner.planner_models import (
    PlannerState,
)

from app.services.planner.goal_decomposer import (
    GoalDecomposer,
)

from app.services.planner.plan_registry import (
    PlanRegistry,
)


class PlannerService:

    def __init__(self):

        self.decomposer = GoalDecomposer()

        self.registry = PlanRegistry()

    # ----------------------------------
    # Existing Planner API
    # ----------------------------------

    def create_plan(
        self,
        goal: str
    ):

        decomposition = (
            self.decomposer.decompose(goal)
        )

        intent = decomposition["intent"]

        steps = self.registry.get_plan(
            intent
        )

        return {

            "success": True,

            "goal": goal,

            "intent": intent,

            "steps": steps
        }

    # ----------------------------------
    # Brain Intelligence API
    # ----------------------------------

    def analyze(
        self,
        decision: DecisionState,
        reasoning: ReasoningState,
        state: PlannerState,
    ) -> PlannerState:

        plan = self.create_plan(
            decision.selected_option
        )

        state.execution_steps = plan["steps"]

        state.execution_order = list(
            plan["steps"]
        )

        state.estimated_outputs = list(
            reasoning.conclusions
        )

        state.dependencies = list(
            decision.accepted_constraints
        )

        state.priorities = [

            "Correctness",

            "Reliability",

            "Performance",
        ]

        state.milestones = [

            "Planning Complete",

            "Execution Ready",
        ]

        state.parallel_tasks = []

        state.blocked_tasks = []

        state.completion_criteria = [

            "All execution steps completed",

            "Verification successful",
        ]

        state.confidence = (
            decision.confidence
        )

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state