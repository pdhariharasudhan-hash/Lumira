class CheckpointResumeProposalService:
    """Create a non-mutating resume proposal from a verified checkpoint."""

    def propose(self, checkpoint):
        allowed = checkpoint.get("resume_candidate") is True
        return {
            "success": True,
            "resume_allowed": allowed,
            "run_id": checkpoint.get("run_id"),
            "safe_resume_point": checkpoint.get("safe_resume_point") if allowed else None,
            "requires_guarded_resume": allowed,
            "reason": checkpoint.get("reason") if not allowed else None,
        }
