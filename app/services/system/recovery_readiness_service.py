class RecoveryReadinessService:
    """Determine whether a task has enough evidence for targeted recovery."""

    def evaluate(self, recovery_package):
        evidence = recovery_package.get("evidence", {})
        analysis = recovery_package.get("analysis", {})
        focus = analysis.get("recovery_focus")
        ready = focus in {"resolve_blocker", "inspect_result", "inspect_task_execution"}
        return {
            "success": True,
            "ready": ready,
            "task_id": evidence.get("task_id"),
            "reason": focus if ready else "insufficient_recovery_evidence",
        }
