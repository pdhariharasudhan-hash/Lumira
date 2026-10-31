class TaskRecoveryAnalysisService:
    """Convert persisted task evidence into deterministic recovery findings."""

    def analyze(self, evidence):
        status = evidence.get("status")
        blocker = evidence.get("blocker")
        result = evidence.get("result")
        finding = "no_failure_evidence"
        if status == "failed":
            finding = "task_failed"
        elif status == "blocked":
            finding = "task_blocked"
        return {
            "success": True,
            "finding": finding,
            "has_blocker": bool(blocker),
            "has_result": bool(result),
            "recovery_focus": "resolve_blocker" if blocker else ("inspect_result" if result else "inspect_task_execution"),
        }
