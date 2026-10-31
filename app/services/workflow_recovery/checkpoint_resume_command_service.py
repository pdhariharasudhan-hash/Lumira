class CheckpointResumeCommandService:
    """Translate a verified checkpoint decision into an explicit guarded command."""

    def build(self, decision, run_id):
        if not decision.get("resume_candidate"):
            return {
                "success": True,
                "command_ready": False,
                "run_id": run_id,
                "reason": decision.get("reason", "checkpoint_not_resumable"),
            }
        return {
            "success": True,
            "command_ready": True,
            "run_id": run_id,
            "operation": "guarded_resume",
            "safe_resume_point": decision.get("safe_resume_point"),
        }
