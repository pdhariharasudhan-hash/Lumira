"""
learning_service.py

Implements Lumira's Learning Engine.
"""

from datetime import datetime

from app.services.learning.learning_models import (
    LearningState,
)

from app.services.reflection.reflection_models import (
    ReflectionState,
)

from app.services.modes.models.mode_state import (
    ModeState,
)


class LearningService:

    # ----------------------------------
    # Mode-aware Learning
    # ----------------------------------

    def _recommendation_for_mode(
        self,
        mode: ModeState | None,
    ) -> str | None:
        """
        Return deterministic mode-specific
        learning guidance.

        Mode provides learning context only.
        Reflection remains authoritative.
        """

        if mode is None:
            return None

        recommendations = {
            "builder":
                "Reuse validated implementation patterns.",

            "research":
                "Reuse validated evidence-gathering patterns.",

            "generator":
                "Reuse validated artifact-generation patterns.",

            "creator":
                "Reuse validated content-generation patterns.",

            "growth":
                "Reuse validated strategic patterns.",

            "operations":
                "Reuse validated operational patterns.",

            "assistant":
                "Reuse validated user-alignment patterns.",
        }

        return recommendations.get(
            mode.active_mode
        )

    def _knowledge_update_for_mode(
        self,
        mode: ModeState | None,
    ) -> str | None:
        """
        Return deterministic mode-specific
        knowledge classification.
        """

        if mode is None:
            return None

        updates = {
            "builder":
                "Implementation knowledge updated.",

            "research":
                "Evidence knowledge updated.",

            "generator":
                "Artifact knowledge updated.",

            "creator":
                "Content knowledge updated.",

            "growth":
                "Strategy knowledge updated.",

            "operations":
                "Operational knowledge updated.",

            "assistant":
                "User-alignment knowledge updated.",
        }

        return updates.get(
            mode.active_mode
        )

    def _future_action_for_mode(
        self,
        mode: ModeState | None,
    ) -> str | None:
        """
        Return deterministic mode-specific
        future execution guidance.
        """

        if mode is None:
            return None

        actions = {
            "builder":
                "Validate implementation patterns before reuse.",

            "research":
                "Validate evidence before reusing conclusions.",

            "generator":
                "Validate artifacts before reuse.",

            "creator":
                "Refine content before reuse.",

            "growth":
                "Revalidate strategic assumptions before reuse.",

            "operations":
                "Revalidate runtime conditions before reuse.",

            "assistant":
                "Revalidate user requirements before reuse.",
        }

        return actions.get(
            mode.active_mode
        )

    def analyze(
        self,
        reflection: ReflectionState,
        state: LearningState,
        mode: ModeState | None = None,
    ) -> LearningState:

        state.lessons = list(
            reflection.improvements
        )

        state.successful_patterns = list(
            reflection.strengths
        )

        state.failed_patterns = list(
            reflection.weaknesses
        )

        state.recommendations = [

            "Reuse successful strategies.",

            "Improve weak reasoning paths."
        ]

        mode_recommendation = (
            self._recommendation_for_mode(mode)
        )

        if mode_recommendation:
            state.recommendations.append(
                mode_recommendation
            )

        state.knowledge_updates = [

            "Runtime knowledge updated."
        ]

        mode_knowledge = (
            self._knowledge_update_for_mode(mode)
        )

        if mode_knowledge:
            state.knowledge_updates.append(
                mode_knowledge
            )

        state.future_actions = [

            "Apply lessons to next execution."
        ]

        mode_action = (
            self._future_action_for_mode(mode)
        )

        if mode_action:
            state.future_actions.append(
                mode_action
            )

        state.confidence = (
            reflection.confidence
        )

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state