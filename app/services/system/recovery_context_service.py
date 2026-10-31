class RecoveryContextService:
    """Build a bounded context package when execution needs recovery."""

    def __init__(self, decision_service, policy_service, learning_service):
        self.decision_service = decision_service
        self.policy_service = policy_service
        self.learning_service = learning_service

    def build(self, project_id=None):
        decision = self.decision_service.snapshot(project_id)
        policy = self.policy_service.evaluate(decision["recommendation"], project_id)
        learning = self.learning_service.recommend(project_id)
        recovery_required = not policy.get("execution_allowed", True)
        return {
            "success": True,
            "recovery_required": recovery_required,
            "reason": policy.get("reason"),
            "recommended_action": policy.get("recommendation"),
            "decision": {"state": decision.get("state"), "recommendation": decision.get("recommendation")},
            "learning": {"pattern": learning.get("pattern"), "recommendation": learning.get("recommendation")},
        }
