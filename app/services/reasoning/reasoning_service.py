"""
reasoning_service.py

Implements Lumira's Reasoning Engine.

The Reasoning Engine consumes the structured outputs
of previous Intelligence modules and derives logical
conclusions.

Ownership:
Handoff 11 - Reasoning Engine
"""

from datetime import datetime

from app.services.reasoning.reasoning_models import (
    ReasoningState,
)

from app.services.conversation.conversation_models import (
    ConversationState,
)

from app.services.goals.goal_models import (
    GoalState,
)

from app.services.objective.objective_models import (
    ObjectiveState,
)

from app.services.context.context_models import (
    ContextState,
)

from app.services.constraints.constraint_models import (
    ConstraintState,
)


class ReasoningService:
    """
    Runtime Reasoning Engine.

    Uses structured information from previous
    intelligence modules to derive logical
    conclusions.
    """

    def analyze(
        self,
        conversation: ConversationState,
        goal: GoalState,
        objective: ObjectiveState,
        context: ContextState,
        constraints: ConstraintState,
        state: ReasoningState,
    ) -> ReasoningState:

        state.facts = self._extract_facts(
            conversation,
            goal,
            objective,
            context,
            constraints,
        )

        state.assumptions = self._build_assumptions(
            context,
            constraints,
        )

        state.alternatives = self._generate_alternatives(
            context,
        )

        state.conclusions = self._derive_conclusions(
            goal,
            objective,
            context,
            constraints,
        )

        state.unresolved_questions = (
            self._find_missing_information(
                constraints
            )
        )

        state.reasoning_trace = (
            self._build_trace(state)
        )

        state.confidence = (
            self._calculate_confidence(state)
        )

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state

    # ----------------------------------
    # Private Methods
    # ----------------------------------

    def _extract_facts(
        self,
        conversation,
        goal,
        objective,
        context,
        constraints,
    ) -> list[str]:

        facts = []

        if conversation.current_topic:
            facts.append(
                f"Topic: {conversation.current_topic}"
            )

        if goal.primary_goal:
            facts.append(
                f"Goal: {goal.primary_goal}"
            )

        if objective.primary_objective:
            facts.append(
                f"Objective: {objective.primary_objective}"
            )

        if context.project_type:
            facts.append(
                f"Project Type: {context.project_type}"
            )

        if context.framework:
            facts.append(
                f"Framework: {context.framework}"
            )

        facts.extend(
            constraints.technical_constraints
        )

        return facts

    def _build_assumptions(
        self,
        context,
        constraints,
    ) -> list[str]:

        assumptions = list(
            constraints.assumptions
        )

        if context.environment:
            assumptions.append(
                f"Environment: {context.environment}"
            )

        return assumptions

    def _generate_alternatives(
        self,
        context,
    ) -> list[str]:

        alternatives = []

        if context.framework == "FastAPI":

            alternatives.extend(
                [
                    "Flask",
                    "Django",
                ]
            )

        elif context.framework == "React":

            alternatives.extend(
                [
                    "Vue",
                    "Angular",
                ]
            )

        return alternatives

    def _derive_conclusions(
        self,
        goal,
        objective,
        context,
        constraints,
    ) -> list[str]:

        conclusions = []

        if context.project_type:

            conclusions.append(
                f"Project identified as {context.project_type}."
            )

        if constraints.missing_information:

            conclusions.append(
                "Additional information is required before execution."
            )

        else:

            conclusions.append(
                "Enough information exists to continue planning."
            )

        return conclusions

    def _find_missing_information(
        self,
        constraints,
    ) -> list[str]:

        return list(
            constraints.missing_information
        )

    def _build_trace(
        self,
        state,
    ) -> list[str]:

        return [

            "Collected facts.",

            "Generated assumptions.",

            "Evaluated alternatives.",

            "Derived conclusions."
        ]

    def _calculate_confidence(
        self,
        state,
    ) -> float:

        score = 0.5

        if state.facts:
            score += 0.15

        if state.conclusions:
            score += 0.20

        if not state.unresolved_questions:
            score += 0.15

        return min(score, 1.0)