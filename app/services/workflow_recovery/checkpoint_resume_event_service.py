from datetime import UTC, datetime

class CheckpointResumeEventService:
    """Create a normalized event payload for existing history/event storage."""

    def build(self, session_id, run_id, preflight, deduplication):
        command = preflight.get("command", {})
        return {
            "event_type": "checkpoint_resume_preflight",
            "session_id": session_id,
            "run_id": run_id,
            "command_ready": command.get("command_ready", False),
            "safe_resume_point": command.get("safe_resume_point"),
            "duplicate": deduplication.get("duplicate", False),
            "reason": deduplication.get("reason") or preflight.get("decision", {}).get("reason"),
            "created_at": datetime.now(UTC).isoformat(),
        }
