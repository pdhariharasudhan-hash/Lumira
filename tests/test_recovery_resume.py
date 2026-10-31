from app.services.system.recovery_completion_service import RecoveryCompletionService

def test_incomplete_recovery_cannot_recheck():
    result = RecoveryCompletionService().evaluate(
        ["inspect_blocker_details"],
        {"steps": ["inspect_blocker_details", "resolve_or_replace_dependency"]},
    )
    assert result["ready_for_recheck"] is False
    assert result["remaining_steps"] == ["resolve_or_replace_dependency"]

def test_complete_recovery_is_ready_for_recheck():
    steps = ["inspect_execution_result", "identify_failure_condition"]
    result = RecoveryCompletionService().evaluate(steps, {"steps": steps})
    assert result["ready_for_recheck"] is True
