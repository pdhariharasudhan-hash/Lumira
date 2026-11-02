class ExecutionPolicyService:
    """Apply outcome history as a deterministic policy layer."""

    def __init__(self, pattern_service):
        self.pattern_service = pattern_service

    def evaluate(self, recommendation, project_id=None):
        pattern = self.pattern_service.summary(project_id)
        failures = pattern.get("failures", 0)
        successes = pattern.get("successes", 0)
        if failures >= 3 and failures > successes:
            return {
                "success": True,
                "recommendation": "review_recent_failures",
                "execution_allowed": False,
                "reason": "repeated_failures",
                "pattern": pattern,
            }
        return {
            "success": True,
            "recommendation": recommendation,
            "execution_allowed": True,
            "reason": None,
            "pattern": pattern,
        }
