from app.services.system.task_recovery_analysis_service import TaskRecoveryAnalysisService

def test_blocked_task_focuses_on_blocker():
    result = TaskRecoveryAnalysisService().analyze({
        "status": "blocked", "blocker": "missing dependency", "result": None,
    })
    assert result["finding"] == "task_blocked"
    assert result["recovery_focus"] == "resolve_blocker"

def test_failed_task_without_details_requests_execution_inspection():
    result = TaskRecoveryAnalysisService().analyze({
        "status": "failed", "blocker": None, "result": None,
    })
    assert result["recovery_focus"] == "inspect_task_execution"
