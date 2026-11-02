class RecoveryNextStepService:
    """Expose one concrete next recovery step without executing it."""

    def next_step(self, task_plan):
        steps = task_plan.get("steps", [])
        return {
            "success": True,
            "next_step": steps[0] if steps else None,
            "remaining_steps": max(0, len(steps) - 1),
        }
