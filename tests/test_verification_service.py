from app.services.prediction.prediction_models import PredictionState
from app.services.planner.planner_models import PlannerState
from app.services.verification.verification_service import VerificationService
from app.services.verification.verification_models import VerificationState


def test_verification_blocks_missing_plan():
    result = VerificationService().analyze(
        PredictionState(),
        PlannerState(),
        VerificationState(),
    )

    assert result.ready_for_execution is False
    assert "Execution plan does not exist." in result.failed_checks


def test_verification_blocks_planner_blockers():
    result = VerificationService().analyze(
        PredictionState(),
        PlannerState(execution_steps=["build"], blocked_tasks=["execute"]),
        VerificationState(),
    )

    assert result.ready_for_execution is False
    assert "Planner blockers unresolved." in result.failed_checks
