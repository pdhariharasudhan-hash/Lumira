"""
planner_service.py

Implements Planner Intelligence for Lumira.

Planner Intelligence converts the Decision Engine's output
into an execution plan.

The Planner MUST respect the Decision Engine.

If the Decision Engine determines that information is missing,
the Planner must not create an execution-ready implementation plan.

Ownership:
Handoff 12 - Planner Intelligence
"""

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

from app.services.modes.models.mode_state import (
    ModeState,
)


class PlannerService:
    """
    Runtime Planner Intelligence.

    Converts DecisionState and ReasoningState into a
    structured PlannerState.
    """

    def __init__(self) -> None:

        self.decomposer = GoalDecomposer()

        self.registry = PlanRegistry()

    # ----------------------------------
    # Mode-aware Planning
    # ----------------------------------

    def _priorities_for_mode(
        self,
        mode: ModeState | None,
    ) -> list[str]:
        """
        Return deterministic planning priorities.

        Mode provides execution context only.
        DecisionState remains authoritative.
        """

        priorities = [
            "Correctness",
            "Reliability",
            "Performance",
        ]

        if mode is None:
            return priorities

        mode_priorities = {
            "builder": [
                "Correctness",
                "Reliability",
                "Implementation",
            ],
            "research": [
                "Evidence Quality",
                "Correctness",
                "Source Validation",
            ],
            "generator": [
                "Output Quality",
                "Correctness",
                "Artifact Validity",
            ],
            "creator": [
                "Content Quality",
                "Correctness",
                "Audience Fit",
            ],
            "growth": [
                "Impact",
                "Feasibility",
                "Growth Potential",
            ],
            "operations": [
                "Reliability",
                "Safety",
                "Execution Efficiency",
            ],
            "assistant": [
                "Correctness",
                "Clarity",
                "User Alignment",
            ],
            "personal": priorities,
        }

        return list(
            mode_priorities.get(
                mode.active_mode,
                priorities,
            )
        )

    # ----------------------------------
    # Existing Planner API
    # ----------------------------------

    def create_plan(
        self,
        goal: str,
    ):
        """
        Create an execution plan for a goal.

        This method remains available for the existing
        planner API and is separate from Brain-aware planning.
        """

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
            "steps": steps,
        }

    # ----------------------------------
    # Brain Intelligence API
    # ----------------------------------

    def analyze(
        self,
        decision: DecisionState,
        reasoning: ReasoningState,
        state: PlannerState,
        mode: ModeState | None = None,
    ) -> PlannerState:
        """
        Convert DecisionState into a Brain execution plan.

        The Planner follows the Decision Engine's next_action.

        If required information is missing, execution planning
        is blocked and the Planner creates an information-
        gathering plan instead.
        """

        # ----------------------------------
        # Reset Runtime Planning State
        # ----------------------------------

        state.execution_steps = []

        state.dependencies = list(
            decision.accepted_constraints
        )

        state.priorities = (
            self._priorities_for_mode(mode)
        )

        state.milestones = []

        state.estimated_outputs = []

        state.execution_order = []

        state.parallel_tasks = []

        state.blocked_tasks = []

        state.completion_criteria = []

        # ----------------------------------
        # Check Decision Gate
        # ----------------------------------

        next_action = (
            decision.next_action.strip().lower()
        )

        # ----------------------------------
        # Missing Information Path
        # ----------------------------------

        if (
            "collect missing information"
            in next_action
        ):

            state.execution_steps = [
                "collect_missing_information",
            ]

            state.execution_order = [
                "collect_missing_information",
            ]

            state.milestones = [
                "Missing Information Identified",
                "Required Information Collected",
            ]

            state.estimated_outputs = list(
                reasoning.unresolved_questions
            )

            state.blocked_tasks = [
                "builder",
                "code",
                "execute",
                "save_project",
            ]

            state.completion_criteria = [
                "All required information collected",
                "Execution blockers resolved",
            ]

            state.parallel_tasks = []

            state.confidence = (
                decision.confidence
            )

            state.last_updated = (
                datetime.utcnow().isoformat()
            )

            return state

        # ----------------------------------
        # Normal Planning Path
        # ----------------------------------

        plan = self.create_plan(
            decision.selected_option
        )

        state.execution_steps = list(
            plan["steps"]
        )

        state.execution_order = list(
            plan["steps"]
        )

        state.estimated_outputs = list(
            reasoning.conclusions
        )

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