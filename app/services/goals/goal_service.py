"""
goal_service.py

Implements the runtime Goal Manager for Lumira.

This service analyzes the current conversation and
extracts the user's primary goal.

It updates only GoalState.

Ownership:
Handoff 11 - Goal Manager
"""

from datetime import datetime, timezone

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

        if state.primary_goal and text.lower().startswith(("add ", "make it ", "change it ", "update it ", "continue ")):
            state.confidence = max(state.confidence, 0.75)
            state.last_updated = datetime.now(timezone.utc).isoformat()
            return state

        state.primary_goal = self._extract_goal(text)

        state.goal_type = self._detect_goal_type(text)

        state.goal_category = self._detect_category(text)

        state.priority = self._detect_priority(text)

        state.is_long_term = self._is_long_term(text)

        state.completed = False

        state.confidence = self._calculate_confidence(text)

        state.last_updated = (
            datetime.now(timezone.utc).isoformat()
        )

        return state

    # ---------------------------------
    # Private Methods
    # ---------------------------------

    def _normalize(
        self,
        text: str,
    ) -> str:
        """Bound and normalize input before classification."""
        if not isinstance(text, str):
            return ""
        return text.strip()[:10_000]

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

        software_terms = ("api", "website", "app", "software", "backend", "frontend", "code")
        hardware_terms = ("drone", "robot", "circuit", "pcb", "esp32", "arduino", "raspberry pi")
        business_terms = ("business", "revenue", "customer", "market", "startup", "sales")
        learning_terms = ("learn", "study", "exam", "course", "school", "physics", "math")

        if any(term in lowered for term in software_terms):
            return "software"
        if any(term in lowered for term in hardware_terms):
            return "hardware"
        if any(term in lowered for term in business_terms):
            return "business"
        if any(term in lowered for term in learning_terms):
            return "learning"
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
