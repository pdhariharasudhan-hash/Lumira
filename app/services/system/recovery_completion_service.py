class RecoveryCompletionService:
    """Decide whether a recovery plan has reached a valid recheck point."""

    def evaluate(self, completed_steps, task_plan):
        steps = task_plan.get("steps", [])
        completed = completed_steps or []
        if not isinstance(completed, list):
            raise ValueError("completed_steps must be a list")
        unknown = [step for step in completed if step not in steps]
        if unknown:
            raise ValueError("completed_steps contains steps outside the recovery plan")
        remaining = [step for step in steps if step not in completed]
        return {
            "success": True,
            "ready_for_recheck": not remaining,
            "completed_steps": completed,
            "remaining_steps": remaining,
        }
