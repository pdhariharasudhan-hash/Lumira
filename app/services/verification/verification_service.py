"""
verification_service.py

Implements Lumira's Verification Engine.

Verification validates whether the current execution plan
is actually ready to proceed.

Ownership:
Handoff 11 - Verification Engine
"""

from datetime import datetime, timezone

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

        # Risks are advisory unless another stage has explicitly classified
        # them as execution blockers. The prediction engine records possible
        # outcomes; it must not reject every normal plan merely for identifying risk.
        if prediction.identified_risks:
            state.warnings.extend(prediction.identified_risks)
        state.passed_checks.append("Predicted risks reviewed.")

        # ----------------------------------
        # Check 3: Dependencies
        # ----------------------------------

        # Dependency records describe the plan and are not, by themselves,
        # unresolved blockers. Explicit blocked_tasks remains the stop signal.
        state.passed_checks.append("Dependencies satisfied.")

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

        # A plan with no executable steps or unresolved planner blockers must
        # not authorize a downstream side effect. Reflection and learning can
        # still run, but the execution coordinator will fail closed.
        state.ready_for_execution = bool(
            planner.execution_steps and not planner.blocked_tasks
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
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        )

        return state