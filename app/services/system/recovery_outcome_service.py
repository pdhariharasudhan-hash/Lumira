class RecoveryOutcomeService:
    """Classify a recorded recovery attempt without guessing."""

    def classify(self, record):
        if record.get("applied"):
            outcome = "resumed"
        elif record.get("transition_allowed"):
            outcome = "approved_not_applied"
        elif record.get("resume_allowed") is False:
            outcome = "policy_or_recovery_blocked"
        else:
            outcome = "transition_blocked"
        return {"success": True, "recovery_id": record.get("recovery_id"), "outcome": outcome}
