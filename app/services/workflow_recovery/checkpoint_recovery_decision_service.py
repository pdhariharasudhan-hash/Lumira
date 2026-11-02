class CheckpointRecoveryDecisionService:
    """Combine session and checkpoint guards into one fail-closed decision."""

    def decide(self, session_guard, checkpoint_integrity):
        allowed = bool(session_guard.get("allowed")) and bool(checkpoint_integrity.get("checkpoint_valid"))
        return {
            "success": True,
            "resume_candidate": allowed,
            "safe_resume_point": checkpoint_integrity.get("safe_resume_point") if allowed else None,
            "requires_manual_reconciliation": checkpoint_integrity.get("requires_manual_reconciliation", False),
            "reason": None if allowed else (
                checkpoint_integrity.get("reason") or session_guard.get("reason") or "checkpoint_not_resumable"
            ),
        }
