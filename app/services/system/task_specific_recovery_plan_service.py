class TaskSpecificRecoveryPlanService:
    """Generate deterministic recovery steps from concrete task evidence."""

    def plan(self, recovery_package):
        evidence = recovery_package.get("evidence", {})
        analysis = recovery_package.get("analysis", {})
        focus = analysis.get("recovery_focus")

        steps = []
        if focus == "resolve_blocker":
            steps = [
                "inspect_blocker_details",
                "resolve_or_replace_dependency",
                "verify_blocker_cleared",
                "recheck_execution_policy",
            ]
        elif focus == "inspect_result":
            steps = [
                "inspect_execution_result",
                "identify_failure_condition",
                "adjust_execution_strategy",
                "recheck_execution_policy",
            ]
        elif focus == "inspect_task_execution":
            steps = [
                "inspect_task_inputs",
                "inspect_execution_attempt",
                "capture_missing_failure_details",
                "recheck_execution_policy",
            ]

        return {
            "success": True,
            "workflow_id": evidence.get("workflow_id"),
            "task_id": evidence.get("task_id"),
            "recovery_focus": focus,
            "steps": steps,
        }
