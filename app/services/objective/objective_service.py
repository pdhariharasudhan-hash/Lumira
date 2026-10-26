"""
objective_service.py

Implements the runtime Objective Extraction for Lumira.

This service analyzes the user's goal and determines
the concrete objective that should be achieved.

It updates only ObjectiveState.

Ownership:
Handoff 11 - Objective Extraction
"""

from datetime import datetime, timezone

from app.services.objective.objective_models import (
    ObjectiveState,
)


class ObjectiveService:
    """
    Runtime Objective Extraction.

    Responsible for determining the concrete
    deliverable expected from the user's request.
    """

    def analyze(
        self,
        user_input: str,
        state: ObjectiveState,
    ) -> ObjectiveState:
        """
        Analyze user input and update ObjectiveState.
        """

        text = self._normalize(user_input)

        if not text:
            return state

        if state.primary_objective and text.lower().startswith(("add ", "make it ", "change it ", "update it ", "continue ")):
            state.completion_status = "in_progress"
            state.last_updated = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            return state

        state.primary_objective = self._extract_objective(
            text
        )

        state.expected_output = self._expected_output(
            text
        )

        state.success_criteria = (
            self._success_criteria(text)
        )

        state.dependencies = (
            self._dependencies(text)
        )

        state.completion_status = "pending"

        state.confidence = (
            self._calculate_confidence(text)
        )

        state.last_updated = (
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        )

        return state

    # ---------------------------------
    # Private Methods
    # ---------------------------------

    def _normalize(
        self,
        text: str,
    ) -> str:
        """Bound and normalize input before objective extraction."""
        if not isinstance(text, str):
            return ""
        return text.strip()[:10_000]

    def _extract_objective(
        self,
        text: str,
    ) -> str:

        return text

    def _expected_output(
        self,
        text: str,
    ) -> str:

        lowered = text.lower()

        if "api" in lowered:
            return "Functional REST API"

        if "website" in lowered:
            return "Working Website"

        if "app" in lowered:
            return "Working Application"

        if "drone" in lowered:
            return "Working Hardware Prototype"

        return "Completed Deliverable"

    def _success_criteria(
        self,
        text: str,
    ) -> list[str]:

        return [
            "Objective completed",
            "Deliverable created",
        ]

    def _dependencies(
        self,
        text: str,
    ) -> list[str]:

        lowered = text.lower()

        deps = []

        if "fastapi" in lowered:
            deps.append("FastAPI")

        if "react" in lowered:
            deps.append("React")

        if "flutter" in lowered:
            deps.append("Flutter")

        if "python" in lowered:
            deps.append("Python")

        return deps

    def _calculate_confidence(
        self,
        text: str,
    ) -> float:

        if len(text) > 10:
            return 1.0

        return 0.5