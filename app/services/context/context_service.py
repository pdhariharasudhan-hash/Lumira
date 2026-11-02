"""
context_service.py

Implements the runtime Context Engine for Lumira.

This service analyzes the conversation,
goal and objective to determine the
execution context.

Ownership:
Handoff 11 - Context Engine
"""

from datetime import datetime, timezone

from app.services.context.context_models import (
    ContextState,
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


class ContextService:
    """
    Runtime Context Engine.

    Responsible for determining the
    execution context required by
    later intelligence modules.
    """

    def analyze(
        self,
        conversation: ConversationState,
        goal: GoalState,
        objective: ObjectiveState,
        state: ContextState,
    ) -> ContextState:

        text = (
            f"{conversation.current_topic} "
            f"{goal.primary_goal} "
            f"{objective.primary_objective}"
        ).lower()

        detected_project_type = self._detect_project_type(text)
        if detected_project_type != "general" or not state.project_type:
            state.project_type = detected_project_type

        detected_domain = self._detect_domain(text)
        if detected_domain != "general" or not state.domain:
            state.domain = detected_domain

        state.programming_language = self._detect_language(text) or state.programming_language

        state.framework = self._detect_framework(text) or state.framework

        state.environment = (
            "development"
        )

        state.workspace = (
            "default"
        )

        state.existing_project = state.existing_project or bool(
            conversation.session_id
            and conversation.recent_references
        )

        state.confidence = (
            self._calculate_confidence(text)
        )

        state.last_updated = (
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        )

        return state

    # ----------------------------------

    def _detect_project_type(
        self,
        text: str,
    ) -> str:

        if "api" in text:
            return "api"

        if "website" in text:
            return "website"

        if "app" in text:
            return "application"

        if any(term in text for term in ("drone", "robot", "esp32", "arduino", "circuit", "pcb")):
            return "hardware"

        if any(term in text for term in ("business", "startup", "market", "revenue")):
            return "business"

        if any(term in text for term in ("study", "exam", "course", "school")):
            return "learning"

        return "general"

    def _detect_domain(
        self,
        text: str,
    ) -> str:

        if "expense" in text:
            return "finance"

        if "medical" in text:
            return "healthcare"

        if any(term in text for term in ("education", "study", "exam", "physics", "math")):
            return "education"

        if any(term in text for term in ("robot", "drone", "esp32", "arduino", "pcb", "electronics")):
            return "engineering"

        if any(term in text for term in ("business", "startup", "sales", "market", "revenue")):
            return "business"

        return "general"

    def _detect_language(
        self,
        text: str,
    ) -> str:

        if "python" in text:
            return "Python"

        if "javascript" in text:
            return "JavaScript"

        if "typescript" in text:
            return "TypeScript"

        return ""

    def _detect_framework(
        self,
        text: str,
    ) -> str:

        if "fastapi" in text:
            return "FastAPI"

        if "react" in text:
            return "React"

        if "flutter" in text:
            return "Flutter"

        return ""

    def _calculate_confidence(
        self,
        text: str,
    ) -> float:

        if len(text) > 10:
            return 1.0

        return 0.5
