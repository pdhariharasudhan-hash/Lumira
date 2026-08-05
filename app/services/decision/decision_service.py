"""
decision_service.py

Implements Lumira's Decision Engine.

The Decision Engine evaluates the reasoning output
and selects the most appropriate execution path.

Ownership:
Handoff 11 - Decision Engine
"""

from datetime import datetime

from app.services.decision.decision_models import (
    DecisionState,
)

from app.services.reasoning.reasoning_models import (
    ReasoningState,
)

from app.services.constraints.constraint_models import (
    ConstraintState,
)


class DecisionService:
    """
    Runtime Decision Engine.

    Converts reasoning into an actionable decision.
    """

    def analyze(
        self,
        reasoning: ReasoningState,
        constraints: ConstraintState,
        state: DecisionState,
    ) -> DecisionState:

        state.alternatives_considered = list(
            reasoning.alternatives
        )

        state.accepted_constraints = list(
            constraints.technical_constraints
        )

        state.rejected_constraints = []

        state.tradeoffs = self._build_tradeoffs(
            reasoning,
            constraints,
        )

        state.selected_option = (
            self._select_option(reasoning)
        )

        state.decision_reason = (
            self._decision_reason(reasoning)
        )

        state.next_action = (
            self._next_action(reasoning)
        )

        state.confidence = (
            self._confidence(reasoning)
        )

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state

    # ----------------------------------
    # Private Methods
    # ----------------------------------

    def _select_option(
        self,
        reasoning: ReasoningState,
    ) -> str:

        if reasoning.conclusions:
            return reasoning.conclusions[0]

        return "Continue analysis"

    def _decision_reason(
        self,
        reasoning: ReasoningState,
    ) -> str:

        if reasoning.unresolved_questions:
            return (
                "Decision made with incomplete information."
            )

        return (
            "Decision based on available facts and reasoning."
        )

    def _next_action(
        self,
        reasoning: ReasoningState,
    ) -> str:

        if reasoning.unresolved_questions:
            return (
                "Collect missing information."
            )

        return (
            "Proceed to planning."
        )

    def _build_tradeoffs(
        self,
        reasoning: ReasoningState,
        constraints: ConstraintState,
    ) -> list[str]:

        tradeoffs = []

        if constraints.resource_constraints:
            tradeoffs.append(
                "Resource limitations may affect implementation."
            )

        if constraints.technical_constraints:
            tradeoffs.append(
                "Technical stack limits implementation choices."
            )

        return tradeoffs

    def _confidence(
        self,
        reasoning: ReasoningState,
    ) -> float:

        return reasoning.confidence