class RecoveryPlanService:
    """Turn a recovery context into deterministic recovery steps."""

    def plan(self, context):
        if not context.get("recovery_required"):
            return {"success": True, "recovery_required": False, "steps": []}
        return {
            "success": True,
            "recovery_required": True,
            "steps": [
                "inspect_recent_failures",
                "inspect_active_blockers",
                "review_execution_strategy",
                "update_next_action",
                "recheck_execution_policy",
            ],
        }
