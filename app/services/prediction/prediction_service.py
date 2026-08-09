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

    Predicts likely outcomes, risks, bottlenecks,
    duration, and complexity from the current plan.
    """

    def analyze(
        self,
        planner: PlannerState,
        decision: DecisionState,
        state: PredictionState,
    ) -> PredictionState:
        """
        Analyze the current execution plan and produce
        runtime predictions.
        """

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
                1.0 - decision.confidence,
                2,
            )
        )

        state.confidence = (
            decision.confidence
        )

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state

    # ----------------------------------
    # Expected Outcomes
    # ----------------------------------

    def _expected_outcomes(
        self,
        planner: PlannerState,
    ) -> list[str]:
        """
        Predict expected outputs from the plan.
        """

        return list(
            planner.estimated_outputs
        )

    # ----------------------------------
    # Risk Prediction
    # ----------------------------------

    def _risks(
        self,
        planner: PlannerState,
    ) -> list[str]:
        """
        Identify likely risks resulting from
        the current execution plan.
        """

        risks: list[str] = []

        if planner.blocked_tasks:
            risks.append(
                "Execution may be delayed until "
                "planner blockers are resolved."
            )

        if planner.dependencies:
            risks.append(
                "Execution may be delayed because "
                "required dependencies are unresolved."
            )

        return risks

    # ----------------------------------
    # Bottleneck Prediction
    # ----------------------------------

    def _bottlenecks(
        self,
        planner: PlannerState,
    ) -> list[str]:
        """
        Identify current execution bottlenecks.
        """

        bottlenecks: list[str] = []

        if planner.blocked_tasks:
            bottlenecks.extend(
                planner.blocked_tasks
            )

        if planner.dependencies:
            bottlenecks.extend(
                planner.dependencies
            )

        return bottlenecks

    # ----------------------------------
    # Duration Estimation
    # ----------------------------------

    def _duration(
        self,
        planner: PlannerState,
    ) -> str:
        """
        Estimate execution duration from
        the number of planned steps.
        """

        step_count = len(
            planner.execution_steps
        )

        if step_count < 5:
            return "Short"

        if step_count < 10:
            return "Medium"

        return "Long"

    # ----------------------------------
    # Complexity Estimation
    # ----------------------------------

    def _complexity(
        self,
        planner: PlannerState,
    ) -> str:
        """
        Estimate execution complexity from
        the number of planned steps.
        """

        step_count = len(
            planner.execution_steps
        )

        if step_count < 5:
            return "Low"

        if step_count < 10:
            return "Medium"

        return "High"