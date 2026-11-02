from app.services.workflow_recovery.checkpoint_resume_execution_gate_service import CheckpointResumeExecutionGateService
from app.services.workflow_recovery.recovery_resume_deduplication_service import RecoveryResumeDeduplicationService

def test_duplicate_resume_request_is_rejected():
    result = RecoveryResumeDeduplicationService().evaluate("run-1", "req-1", ["req-1"])
    assert result["duplicate"] is True
    assert result["resume_allowed"] is False

def test_execution_gate_fails_closed_when_preflight_fails():
    result = CheckpointResumeExecutionGateService().evaluate(
        {"command": {"command_ready": False}, "decision": {"reason": "uncertain_side_effect"}},
        {"resume_allowed": True},
    )
    assert result["execute_resume"] is False
    assert result["reason"] == "uncertain_side_effect"
