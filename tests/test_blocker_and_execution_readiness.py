from app.services.work_items.blocker_insights_service import BlockerInsightsService
from app.services.system.execution_readiness_service import ExecutionReadinessService

class FakeBlockers:
    def list(self, **kwargs):
        return {"success": True, "count": 2, "blockers": [{"kind": "goal"}, {"kind": "task"}]}

class FakeActions:
    def ready(self, **kwargs):
        return {"success": True, "count": 3, "actions": [{}, {}, {}]}

def test_blocker_insights():
    result = BlockerInsightsService(FakeBlockers()).summary()
    assert result["total"] == 2
    assert result["by_kind"] == {"goal": 1, "task": 1}

def test_execution_readiness():
    result = ExecutionReadinessService(FakeActions(), FakeBlockers()).status()
    assert result["state"] == "blocked"
    assert result["ready_action_count"] == 3
