from datetime import UTC, datetime

class CheckpointRecoveryAuditService:
    """Create a bounded audit event for checkpoint recovery decisions."""

    def record(self, decision, session_id, run_id):
        return {
            "success": True,
            "event": {
                "event_type": "checkpoint_recovery_decision",
                "session_id": session_id,
                "run_id": run_id,
                "resume_candidate": decision.get("resume_candidate", False),
                "safe_resume_point": decision.get("safe_resume_point"),
                "reason": decision.get("reason"),
                "recorded_at": datetime.now(UTC).isoformat(),
            },
        }
