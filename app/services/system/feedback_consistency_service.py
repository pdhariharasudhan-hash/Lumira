class FeedbackConsistencyService:
    """Check that execution feedback created both event and memory records."""

    def inspect(self, feedback_result):
        event_ok = bool(feedback_result.get("event", {}).get("success"))
        memory_ok = bool(feedback_result.get("memory", {}).get("success"))
        return {
            "success": event_ok and memory_ok,
            "event_persisted": event_ok,
            "memory_persisted": memory_ok,
            "state": "consistent" if event_ok and memory_ok else "partial_failure",
        }
