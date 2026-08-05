"""
constraint_service.py

Implements the Constraint Analysis engine.

This service extracts all constraints affecting
the user's request based on the outputs of the
previous intelligence modules.

Ownership:
Handoff 11 - Constraint Analysis
"""

from datetime import datetime

from app.services.constraints.constraint_models import (
    ConstraintState,
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


class ConstraintService:
    """
    Runtime Constraint Analysis.

    Determines all explicit and implicit
    constraints affecting execution.
    """

    def analyze(
        self,
        conversation: ConversationState,
        goal: GoalState,
        objective: ObjectiveState,
        context: ContextState,
        state: ConstraintState,
    ) -> ConstraintState:

        text = " ".join(
            [
                conversation.current_topic,
                goal.primary_goal,
                objective.primary_objective,
                context.project_type,
                context.domain,
                context.programming_language,
                context.framework,
            ]
        ).lower()

        state.functional_constraints = (
            self._functional_constraints(text)
        )

        state.technical_constraints = (
            self._technical_constraints(context)
        )

        state.resource_constraints = (
            self._resource_constraints(text)
        )

        state.platform_constraints = (
            self._platform_constraints(context)
        )

        state.user_constraints = (
            self._user_constraints(text)
        )

        state.assumptions = (
            self._assumptions(context)
        )

        state.risks = (
            self._risks(text)
        )

        state.missing_information = (
            self._missing_information(context)
        )

        state.confidence = (
            self._confidence(state)
        )

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state

    # ---------------------------------
    # Private Methods
    # ---------------------------------

    def _functional_constraints(
        self,
        text: str,
    ) -> list[str]:

        constraints = []

        if "api" in text:
            constraints.append(
                "Provide REST API endpoints."
            )

        if "crud" in text:
            constraints.append(
                "Support CRUD operations."
            )

        return constraints

    def _technical_constraints(
        self,
        context: ContextState,
    ) -> list[str]:

        constraints = []

        if context.programming_language:
            constraints.append(
                context.programming_language
            )

        if context.framework:
            constraints.append(
                context.framework
            )

        return constraints

    def _resource_constraints(
        self,
        text: str,
    ) -> list[str]:

        constraints = []

        if "low budget" in text:
            constraints.append(
                "Budget constrained."
            )

        if "offline" in text:
            constraints.append(
                "Offline operation required."
            )

        return constraints

    def _platform_constraints(
        self,
        context: ContextState,
    ) -> list[str]:

        constraints = []

        if context.project_type:
            constraints.append(
                context.project_type
            )

        return constraints

    def _user_constraints(
        self,
        text: str,
    ) -> list[str]:

        constraints = []

        if "fast" in text:
            constraints.append(
                "Prioritize speed."
            )

        if "secure" in text:
            constraints.append(
                "Prioritize security."
            )

        return constraints

    def _assumptions(
        self,
        context: ContextState,
    ) -> list[str]:

        assumptions = [
            "Development environment available."
        ]

        if context.framework:
            assumptions.append(
                "Framework is installed."
            )

        return assumptions

    def _risks(
        self,
        text: str,
    ) -> list[str]:

        risks = []

        if "prototype" in text:
            risks.append(
                "Prototype may not be production ready."
            )

        return risks

    def _missing_information(
        self,
        context: ContextState,
    ) -> list[str]:

        missing = []

        if not context.programming_language:
            missing.append(
                "Programming language not specified."
            )

        if not context.framework:
            missing.append(
                "Framework not specified."
            )

        return missing

    def _confidence(
        self,
        state: ConstraintState,
    ) -> float:

        score = 0.5

        if state.technical_constraints:
            score += 0.2

        if state.functional_constraints:
            score += 0.2

        if not state.missing_information:
            score += 0.1

        return min(score, 1.0)