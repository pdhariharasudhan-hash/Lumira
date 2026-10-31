class CheckpointResumeResultService:
    """Normalize guarded resume outcomes for routes and callers."""

    def summarize(self, adapter_result):
        result = adapter_result.get("result") or {}
        return {
            "success": adapter_result.get("success", False),
            "state": adapter_result.get("state", "blocked"),
            "run_id": adapter_result.get("run_id"),
            "code": result.get("code"),
            "last_completed_stage": result.get("last_completed_stage"),
            "current_stage": result.get("current_stage"),
        }
