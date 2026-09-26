"""
reflection_service.py

Implements Lumira's Reflection Engine.
"""

from datetime import datetime

from app.services.reflection.reflection_models import (
    ReflectionState,
)

from app.services.verification.verification_models import (
    VerificationState,
)

from app.services.prediction.prediction_models import (
    PredictionState,
)

from app.services.modes.models.mode_state import (
    ModeState,
)


class ReflectionService:

    # ----------------------------------
    # Mode-aware Reflection
    # ----------------------------------

    def _observation_for_mode(
        self,
        mode: ModeState | None,
    ) -> str | None:
        """
        Return deterministic reflection context
        for the active operating mode.

        Mode provides reflection context only.
        Verification and Prediction remain
        authoritative.
        """

        if mode is None:
            return None

        observations = {
            "builder":
                "Reflection focused on implementation quality.",
            "research":
                "Reflection focused on evidence quality.",
            "generator":
                "Reflection focused on artifact quality.",
            "creator":
                "Reflection focused on content quality.",
            "growth":
                "Reflection focused on strategic assumptions.",
            "operations":
                "Reflection focused on operational reliability.",
            "assistant":
                "Reflection focused on user alignment.",
        }

        return observations.get(
            mode.active_mode
        )

    def _improvement_for_mode(
        self,
        mode: ModeState | None,
    ) -> str | None:
        """
        Return deterministic mode-specific
        improvement guidance.
        """

        if mode is None:
            return None

        improvements = {
            "builder":
                "Improve implementation validation.",
            "research":
                "Improve evidence validation.",
            "generator":
                "Improve artifact validation.",
            "creator":
                "Improve content refinement.",
            "growth":
                "Improve assumption validation.",
            "operations":
                "Improve runtime validation.",
            "assistant":
                "Improve requirement clarity.",
        }

        return improvements.get(
            mode.active_mode
        )

    def analyze(
        self,
        verification: VerificationState,
        prediction: PredictionState,
        state: ReflectionState,
        mode: ModeState | None = None,
    ) -> ReflectionState:

        state.observations = [

            "Reflection completed."
        ]

        mode_observation = (
            self._observation_for_mode(mode)
        )

        if mode_observation:
            state.observations.append(
                mode_observation
            )

        if verification.ready_for_execution:

            state.strengths.append(
                "Execution readiness confirmed."
            )

        else:

            state.weaknesses.append(
                "Execution readiness not achieved."
            )

        state.missed_opportunities = []

        state.improvements = [

            "Improve prediction accuracy.",

            "Reduce execution risks."
        ]

        mode_improvement = (
            self._improvement_for_mode(mode)
        )

        if mode_improvement:
            state.improvements.append(
                mode_improvement
            )

        state.overall_quality = (

            "Good"

            if verification.ready_for_execution

            else

            "Needs Improvement"
        )

        state.confidence = (
            prediction.confidence
        )

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state