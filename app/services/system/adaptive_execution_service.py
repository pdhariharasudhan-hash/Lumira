class AdaptiveExecutionService:
    """Combine current state, learning history and execution policy."""

    def __init__(self, decision_service, learning_service, policy_service=None):
        self.decision_service = decision_service
        self.learning_service = learning_service
        self.policy_service = policy_service

    def guidance(self, project_id=None):
        decision = self.decision_service.snapshot(project_id)
        learning = self.learning_service.recommend(project_id)

        if learning.get("pattern", {}).get("pattern") == "failure_trend":
            recommendation = learning["recommendation"]
            source = "learning"
        else:
            recommendation = decision["recommendation"]
            source = "current_state"

        policy = (
            self.policy_service.evaluate(recommendation, project_id)
            if self.policy_service else
            {"recommendation": recommendation, "execution_allowed": True}
        )

        return {
            "success": True,
            "recommendation": policy["recommendation"],
            "source": "execution_policy" if policy.get("reason") else source,
            "execution_allowed": policy.get("execution_allowed", True),
            "decision": decision,
            "learning": learning,
            "policy": policy,
        }
