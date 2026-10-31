from app.services.system.execution_policy_service import ExecutionPolicyService

class FakePattern:
    def summary(self, project_id=None):
        return {"failures": 4, "successes": 1, "pattern": "failure_trend"}

def test_repeated_failures_block_execution():
    result = ExecutionPolicyService(FakePattern()).evaluate("execute_next_action")
    assert result["execution_allowed"] is False
    assert result["recommendation"] == "review_recent_failures"
