class RecoveryRecheckService:
    """Re-run the execution policy after recovery planning is complete."""

    def __init__(self, policy_service):
        self.policy_service = policy_service

    def recheck(self, recommendation, completion, project_id=None):
        if not completion.get("ready_for_recheck"):
            return {
                "success": True,
                "rechecked": False,
                "execution_allowed": False,
                "reason": "recovery_incomplete",
            }
        policy = self.policy_service.evaluate(recommendation, project_id)
        return {
            "success": True,
            "rechecked": True,
            "execution_allowed": policy.get("execution_allowed", False),
            "recommendation": policy.get("recommendation"),
            "reason": policy.get("reason"),
            "policy": policy,
        }
