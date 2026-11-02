from app.services.system.recovery_transition_apply_service import RecoveryTransitionApplyService

class FakeWorkItems:
    def update_task(self, workflow_id, task_id, status):
        return {"workflow_id": workflow_id, "status": status}

def test_transition_requires_explicit_confirmation():
    service = RecoveryTransitionApplyService(FakeWorkItems())
    result = service.apply({"transition_allowed": True, "workflow_id": "w", "task_id": "t", "proposed_status": "in_progress"})
    assert result["applied"] is False
    assert result["reason"] == "explicit_confirmation_required"

def test_disallowed_transition_is_not_applied():
    service = RecoveryTransitionApplyService(FakeWorkItems())
    result = service.apply({"transition_allowed": False, "reason": "recovery_incomplete"}, True)
    assert result["applied"] is False
    assert result["reason"] == "recovery_incomplete"
