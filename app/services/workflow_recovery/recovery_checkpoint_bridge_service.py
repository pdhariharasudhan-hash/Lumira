class RecoveryCheckpointBridgeService:
    """Bridge session recovery snapshots to an existing guarded workflow run."""

    def __init__(self, session_service, recovery_service):
        self.session_service = session_service
        self.recovery_service = recovery_service

    def inspect(self, session_id, run_id):
        snapshot = self.session_service.snapshot_context(session_id)
        run = self.recovery_service.get_run(run_id)
        if run is None:
            raise KeyError("recovery run not found")

        pending = snapshot.get("pending_tasks", [])
        linked_workflows = set(snapshot.get("recent_workflow_ids", []))
        safe_point = run.get("safe_resume_point")
        resumable = (
            run.get("session_id") == session_id
            and run.get("status") == "failed"
            and run.get("resume_allowed") is True
            and isinstance(safe_point, str)
        )
        return {
            "success": True,
            "session_id": session_id,
            "run_id": run_id,
            "safe_resume_point": safe_point,
            "run_status": run.get("status"),
            "session_linked": run.get("session_id") == session_id,
            "pending_task_count": len(pending),
            "recent_workflow_count": len(linked_workflows),
            "resume_candidate": resumable,
            "reason": None if resumable else "run_not_resumable_from_session_checkpoint",
        }
