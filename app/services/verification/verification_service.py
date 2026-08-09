"""
verification_service.py

Implements Lumira's Verification Engine.

Verification validates whether the current execution plan
is actually ready to proceed.

Ownership:
Handoff 11 - Verification Engine
"""

from datetime import datetime

from app.services.verification.verification_models import (
    VerificationState,
)

from app.services.prediction.prediction_models import (
    PredictionState,
)

from app.services.planner.planner_models import (
    PlannerState,
)


class VerificationService:
    """
    Runtime Verification Engine.

    Verification does not create a plan.

    It evaluates the PredictionState and PlannerState
    and determines whether execution is safe and permitted.
    """

    def analyze(
        self,
        prediction: PredictionState,
        planner: PlannerState,
        state: VerificationState,
    ) -> VerificationState:
        """
        Verify the current execution plan.

        Execution is permitted only when:

        1. A valid execution plan exists.
        2. The planner has no blocked tasks.
        3. No critical prediction risks remain.
        4. Required execution dependencies are satisfied.
        """

        # ----------------------------------
        # Validation Rules
        # ----------------------------------

        state.validation_rules = [
            "All execution steps must complete.",
            "No critical risks should remain.",
            "Expected outputs must be produced.",
            "No planner blockers may remain.",
        ]

        # ----------------------------------
        # Required Checks
        # ----------------------------------

        state.required_checks = [
            "Execution plan exists.",
            "Predicted risks reviewed.",
            "Dependencies satisfied.",
            "Planner blockers resolved.",
        ]

        # ----------------------------------
        # Reset Previous Verification
        # ----------------------------------

        state.passed_checks = []
        state.failed_checks = []
        state.warnings = []

        # ----------------------------------
        # Check 1: Execution Plan
        # ----------------------------------

        if planner.execution_steps:
            state.passed_checks.append(
                "Execution plan exists."
            )
        else:
            state.failed_checks.append(
                "Execution plan does not exist."
            )

        # ----------------------------------
        # Check 2: Predicted Risks
        # ----------------------------------

        if prediction.identified_risks:
            state.warnings.extend(
                prediction.identified_risks
            )

            state.failed_checks.append(
                "Predicted risks require review."
            )
        else:
            state.passed_checks.append(
                "Predicted risks reviewed."
            )

        # ----------------------------------
        # Check 3: Dependencies
        # ----------------------------------

        if planner.dependencies:
            state.failed_checks.append(
                "Execution dependencies require resolution."
            )
        else:
            state.passed_checks.append(
                "Dependencies satisfied."
            )

        # ----------------------------------
        # Check 4: Planner Blockers
        # ----------------------------------

        if planner.blocked_tasks:

            for task in planner.blocked_tasks:
                state.warnings.append(
                    f"Execution blocked: {task}"
                )

            state.failed_checks.append(
                "Planner blockers unresolved."
            )

        else:
            state.passed_checks.append(
                "Planner blockers resolved."
            )

        # ----------------------------------
        # Execution Readiness
        # ----------------------------------

        state.ready_for_execution = (
            len(state.failed_checks) == 0
        )

        # ----------------------------------
        # Confidence
        # ----------------------------------

        state.confidence = min(
            prediction.confidence,
            planner.confidence,
        )

        # ----------------------------------
        # Timestamp
        # ----------------------------------

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state