class FailureGuardService:
    """Escalate repeated failure patterns before normal execution continues."""

    def __init__(self, pattern_service):
        self.pattern_service = pattern_service

    def evaluate(self, project_id=None):
        pattern = self.pattern_service.summary(project_id)
        failures = pattern.get("failures", 0)
        successes = pattern.get("successes", 0)
        guarded = failures >= 3 and failures > successes
        return {
            "success": True,
            "guarded": guarded,
            "reason": "repeated_failures" if guarded else None,
            "pattern": pattern,
        }
