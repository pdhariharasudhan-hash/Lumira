from app.services.system.task_specific_recovery_plan_service import TaskSpecificRecoveryPlanService

def test_blocker_plan_prioritizes_resolution():
    package = {
        "evidence": {"workflow_id": "w", "task_id": "t"},
        "analysis": {"recovery_focus": "resolve_blocker"},
    }
    result = TaskSpecificRecoveryPlanService().plan(package)
    assert result["steps"][0] == "inspect_blocker_details"
    assert result["steps"][-1] == "recheck_execution_policy"

def test_result_plan_prioritizes_diagnosis():
    package = {
        "evidence": {"workflow_id": "w", "task_id": "t"},
        "analysis": {"recovery_focus": "inspect_result"},
    }
    result = TaskSpecificRecoveryPlanService().plan(package)
    assert result["steps"][0] == "inspect_execution_result"
