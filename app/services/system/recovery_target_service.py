class RecoveryTargetService:
    """Select the next concrete workflow task to inspect during recovery."""

    def select(self, context):
        affected = context.get("affected_tasks", [])
        priority = {"failed": 0, "blocked": 1, "in_progress": 2}
        ordered = sorted(affected, key=lambda item: priority.get(item.get("status"), 9))
        return {
            "success": True,
            "target": ordered[0] if ordered else None,
            "reason": "highest_priority_affected_task" if ordered else "no_affected_tasks",
        }
