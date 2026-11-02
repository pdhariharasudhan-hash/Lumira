from app.services.system.recovery_plan_service import RecoveryPlanService

def test_recovery_plan_is_empty_when_not_required():
    result = RecoveryPlanService().plan({"recovery_required": False})
    assert result["steps"] == []

def test_recovery_plan_has_deterministic_steps():
    result = RecoveryPlanService().plan({"recovery_required": True})
    assert result["steps"][0] == "inspect_recent_failures"
    assert result["steps"][-1] == "recheck_execution_policy"
