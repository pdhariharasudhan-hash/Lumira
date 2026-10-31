from __future__ import annotations

from typing import Any


class WorkflowInsightsService:
    """Summarize existing durable workflows without changing their execution state."""

    def __init__(self, workflow_service=None):
        self.workflow_service = workflow_service

    def summary(self, project_id: str | None = None, goal_id: str | None = None) -> dict[str, Any]:
        if self.workflow_service is None:
            from app.services.work_items.work_item_service import WorkItemService
            service = WorkItemService()
        else:
            service = self.workflow_service
        workflows = service.list_workflows(project_id=project_id, goal_id=goal_id, limit=200)
        status_counts: dict[str, int] = {}
        task_total = task_completed = task_blocked = 0
        for workflow in workflows:
            status = str(workflow.get("status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1
            for task in workflow.get("tasks", []):
                if not isinstance(task, dict):
                    continue
                task_total += 1
                task_completed += task.get("status") == "completed"
                task_blocked += task.get("status") == "blocked"
        return {
            "success": True,
            "workflow_count": len(workflows),
            "workflow_status_counts": status_counts,
            "task_total": task_total,
            "task_completed": task_completed,
            "task_blocked": task_blocked,
            "task_completion_rate": round((task_completed / task_total) * 100, 2) if task_total else 0.0,
        }
