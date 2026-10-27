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

from datetime import datetime, timezone

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

    MAX_PLAN_STEPS = 12
    MAX_STEP_LENGTH = 200

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
            "business": [
                "Evidence Quality",
                "Financial Feasibility",
                "Operational Readiness",
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

        if not isinstance(goal, str) or not goal.strip():
            return {
                "success": False,
                "error": "goal must be a non-empty string",
                "goal": "",
                "intent": None,
                "steps": [],
            }
        normalized_goal = goal.strip()[:10_000]
        decomposition = self.decomposer.decompose(normalized_goal)
        intent = decomposition.get("intent")
        steps = self.registry.get_plan(intent) if isinstance(intent, str) else None
        if not isinstance(steps, list) or not steps:
            return {
                "success": False,
                "error": "no registered plan for the selected intent",
                "goal": normalized_goal,
                "intent": intent,
                "steps": [],
            }

        # Plans are data, not trusted execution instructions. Normalize and cap
        # registered steps so a malformed extension cannot create an unbounded plan.
        safe_steps = [
            step.strip()[: self.MAX_STEP_LENGTH]
            for step in steps
            if isinstance(step, str) and step.strip()
        ][: self.MAX_PLAN_STEPS]
        if not safe_steps:
            return {
                "success": False,
                "error": "registered plan contains no valid steps",
                "goal": normalized_goal,
                "intent": intent,
                "steps": [],
            }

        return {
            "success": True,
            "goal": normalized_goal,
            "intent": intent,
            "steps": safe_steps,
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

        # Accepted constraints are requirements, not unresolved dependencies.
        # Only unanswered reasoning questions should block dependency readiness.
        state.dependencies = list(reasoning.unresolved_questions)

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
                datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            )

            return state

        # ----------------------------------
        # Normal Planning Path
        # ----------------------------------

        plan = self.create_plan(decision.selected_option)
        state.parallel_tasks = []

        # A missing or malformed plan is a blocker, not an empty successful plan.
        # Do not advertise readiness unless there are concrete bounded steps.
        if plan.get("success") is not True or not plan.get("steps"):
            reason = str(plan.get("error") or "Planner returned no executable steps")[:300]
            state.execution_steps = []
            state.execution_order = []
            state.estimated_outputs = []
            state.milestones = ["Planning Blocked"]
            state.blocked_tasks = ["planner"]
            state.completion_criteria = [
                "Register or select a supported plan for this intent.",
                "Re-run planning and verify that at least one bounded step exists.",
            ]
            state.dependencies = list(dict.fromkeys([*state.dependencies, reason]))[:50]
            state.confidence = min(max(float(decision.confidence), 0.0), 0.25)
            state.last_updated = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            return state

        steps = plan["steps"][: self.MAX_PLAN_STEPS]
        state.execution_steps = list(steps)
        state.execution_order = list(steps)
        state.estimated_outputs = list(reasoning.conclusions[:50])
        state.milestones = ["Planning Complete", "Execution Ready"]
        state.blocked_tasks = []
        state.completion_criteria = [
            "All execution steps completed",
            "Verification successful",
        ]
        state.confidence = min(max(float(decision.confidence), 0.0), 1.0)
        state.last_updated = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        return state
