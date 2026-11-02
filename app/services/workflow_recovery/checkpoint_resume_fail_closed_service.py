class CheckpointResumeFailClosedService:
    """Single policy check ensuring invalid resume inputs never reach execution."""

    def evaluate(self, session_id, run):
        if not isinstance(session_id, str) or not session_id:
            return {"allowed": False, "reason": "invalid_session_id"}
        if not isinstance(run, dict) or not isinstance(run.get("run_id"), str):
            return {"allowed": False, "reason": "invalid_recovery_run"}
        return {"allowed": True, "reason": None}
