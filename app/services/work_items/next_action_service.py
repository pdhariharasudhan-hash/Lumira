from __future__ import annotations

from typing import Any


class NextActionService:
    """Return dependency-ready workflow tasks as Lumira's immediate action queue."""

    def __init__(self, work_item_service=None):
        self.work_item_service = work_item_service

    def ready(self, project_id: str | None = None, goal_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        if self.work_item_service is None:
            from app.services.work_items.work_item_service import WorkItemService
            service = WorkItemService()
        else:
            service = self.work_item_service
        workflows = service.list_workflows(project_id=project_id, goal_id=goal_id, limit=200)
        actions = []
        for workflow in workflows:
            tasks = {item.get("task_id"): item for item in workflow.get("tasks", []) if isinstance(item, dict)}
            for task in tasks.values():
                if task.get("status") != "pending":
                    continue
                dependencies = task.get("dependencies", [])
                if all(tasks.get(dep, {}).get("status") == "completed" for dep in dependencies):
                    actions.append({"workflow_id": workflow.get("workflow_id"), "goal_id": workflow.get("goal_id"),
                                    "project_id": workflow.get("project_id"), "task_id": task.get("task_id"),
                                    "title": task.get("title")})
        return {"success": True, "count": len(actions), "actions": actions[:max(1, min(limit, 200))]}
