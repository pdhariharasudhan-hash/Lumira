from app.services.system.recovery_target_service import RecoveryTargetService

def test_failed_task_is_selected_before_blocked_task():
    context = {"affected_tasks": [
        {"task_id": "blocked", "status": "blocked"},
        {"task_id": "failed", "status": "failed"},
        {"task_id": "running", "status": "in_progress"},
    ]}
    result = RecoveryTargetService().select(context)
    assert result["target"]["task_id"] == "failed"
