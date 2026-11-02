from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.tasks.quick_task_service import QuickTaskService


class TaskInsightsService:
    """Read-only progress and workload insights for Lumira quick tasks."""

    def __init__(self, task_service=None):
        self.task_service = task_service or QuickTaskService()

    def summary(self) -> dict[str, Any]:
        result = self.task_service.list()
        tasks = result.get("tasks", []) if isinstance(result, dict) else []
        counts = Counter(str(item.get("status", "unknown")) for item in tasks if isinstance(item, dict))
        total = len(tasks)
        completed = counts.get("completed", 0)
        return {
            "success": True,
            "total": total,
            "completed": completed,
            "pending": counts.get("pending", 0),
            "completion_rate": round((completed / total) * 100, 2) if total else 0.0,
            "status_counts": dict(counts),
        }
