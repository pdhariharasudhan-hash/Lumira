"""
prediction_service.py

Implements Lumira's Prediction Engine.

Ownership:
Handoff 11 - Prediction Engine
"""

from datetime import datetime

from app.services.prediction.prediction_models import (
    PredictionState,
)

from app.services.planner.planner_models import (
    PlannerState,
)

from app.services.decision.decision_models import (
    DecisionState,
)


class PredictionService:
    """
    Runtime Prediction Engine.
    """

    def analyze(
        self,
        planner: PlannerState,
        decision: DecisionState,
        state: PredictionState,
    ) -> PredictionState:

        state.expected_outcomes = (
            self._expected_outcomes(
                planner
            )
        )

        state.identified_risks = (
            self._risks(
                planner
            )
        )

        state.bottlenecks = (
            self._bottlenecks(
                planner
            )
        )

        state.estimated_duration = (
            self._duration(
                planner
            )
        )

        state.estimated_complexity = (
            self._complexity(
                planner
            )
        )

        state.success_probability = (
            decision.confidence
        )

        state.failure_probability = (
            round(
                1.0 -
                decision.confidence,
                2
            )
        )

        state.confidence = (
            decision.confidence
        )

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state

    # -----------------------------

    def _expected_outcomes(
        self,
        planner: PlannerState,
    ):

        return list(
            planner.estimated_outputs
        )

    def _risks(
        self,
        planner: PlannerState,
    ):

        risks = []

        if planner.blocked_tasks:

            risks.append(
                "Blocked tasks detected."
            )

        if planner.dependencies:

            risks.append(
                "Execution depends on external requirements."
            )

        return risks

    def _bottlenecks(
        self,
        planner: PlannerState,
    ):

        return list(
            planner.dependencies
        )

    def _duration(
        self,
        planner: PlannerState,
    ):

        if len(
            planner.execution_steps
        ) < 5:

            return "Short"

        if len(
            planner.execution_steps
        ) < 10:

            return "Medium"

        return "Long"

    def _complexity(
        self,
        planner: PlannerState,
    ):

        count = len(
            planner.execution_steps
        )

        if count < 5:

            return "Low"

        if count < 10:

            return "Medium"

        return "High"