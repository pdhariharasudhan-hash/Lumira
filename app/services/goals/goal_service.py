"""
goal_service.py

Implements the runtime Goal Manager for Lumira.

This service analyzes the current conversation and
extracts the user's primary goal.

It updates only GoalState.

Ownership:
Handoff 11 - Goal Manager
"""

from datetime import datetime

from app.services.goals.goal_models import GoalState


class GoalService:
    """
    Runtime Goal Manager.

    Responsible for identifying the user's
    primary objective.
    """

    def analyze(
        self,
        user_input: str,
        state: GoalState,
    ) -> GoalState:
        """
        Analyze user input and update GoalState.
        """

        text = self._normalize(user_input)

        if not text:
            return state

        state.primary_goal = self._extract_goal(text)

        state.goal_type = self._detect_goal_type(text)

        state.goal_category = self._detect_category(text)

        state.priority = self._detect_priority(text)

        state.is_long_term = self._is_long_term(text)

        state.completed = False

        state.confidence = self._calculate_confidence(text)

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state

    # ---------------------------------
    # Private Methods
    # ---------------------------------

    def _normalize(
        self,
        text: str,
    ) -> str:

        return text.strip()

    def _extract_goal(
        self,
        text: str,
    ) -> str:

        return text

    def _detect_goal_type(
        self,
        text: str,
    ) -> str:

        lowered = text.lower()

        if lowered.startswith(
            (
                "build",
                "create",
                "develop",
                "generate",
            )
        ):
            return "creation"

        if lowered.startswith(
            (
                "learn",
                "study",
            )
        ):
            return "learning"

        if lowered.startswith(
            (
                "improve",
                "optimize",
            )
        ):
            return "optimization"

        return "general"

    def _detect_category(
        self,
        text: str,
    ) -> str:

        lowered = text.lower()

        if "api" in lowered:
            return "software"

        if "website" in lowered:
            return "software"

        if "app" in lowered:
            return "software"

        if "drone" in lowered:
            return "hardware"

        if "business" in lowered:
            return "business"

        return "general"

    def _detect_priority(
        self,
        text: str,
    ) -> str:

        lowered = text.lower()

        if (
            "urgent" in lowered
            or "immediately" in lowered
            or "asap" in lowered
        ):
            return "high"

        return "normal"

    def _is_long_term(
        self,
        text: str,
    ) -> bool:

        lowered = text.lower()

        keywords = (
            "career",
            "lifetime",
            "long term",
            "future",
            "become",
        )

        return any(
            keyword in lowered
            for keyword in keywords
        )

    def _calculate_confidence(
        self,
        text: str,
    ) -> float:

        if len(text) > 10:
            return 1.0

        return 0.5