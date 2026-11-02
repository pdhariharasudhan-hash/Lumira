from app.services.workflow_recovery.checkpoint_integrity_service import CheckpointIntegrityService
from app.services.workflow_recovery.checkpoint_recovery_decision_service import CheckpointRecoveryDecisionService

def test_uncertain_side_effect_requires_manual_reconciliation():
    run = {
        "status": "failed", "resume_allowed": True,
        "safe_resume_point": "save_project",
        "stage_records": [{"stage": "save_project", "status": "failed"}],
    }
    result = CheckpointIntegrityService().evaluate(run)
    assert result["checkpoint_valid"] is False
    assert result["requires_manual_reconciliation"] is True

def test_decision_fails_closed_when_session_guard_fails():
    result = CheckpointRecoveryDecisionService().decide(
        {"allowed": False, "reason": "session_run_mismatch"},
        {"checkpoint_valid": True, "safe_resume_point": "validate"},
    )
    assert result["resume_candidate"] is False
    assert result["reason"] == "session_run_mismatch"
