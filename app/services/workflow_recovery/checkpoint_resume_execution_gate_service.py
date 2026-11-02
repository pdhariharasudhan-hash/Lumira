class CheckpointResumeExecutionGateService:
    """Final fail-closed gate before invoking an existing resume operation."""

    def evaluate(self, preflight, deduplication):
        command_ready = preflight.get("command", {}).get("command_ready") is True
        unique = deduplication.get("resume_allowed") is True
        allowed = command_ready and unique
        return {
            "success": True,
            "execute_resume": allowed,
            "reason": None if allowed else (
                deduplication.get("reason") or
                preflight.get("decision", {}).get("reason") or
                "resume_preflight_failed"
            ),
        }
