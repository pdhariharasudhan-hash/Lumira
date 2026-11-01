from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any


class BlockerQueueService:
    """Read-only blocker aggregation for personal goals and workflows.

    The queue is derived from existing durable stores; it does not mutate tasks,
    goals, or retry state.
    """

    TERMINAL_GOAL_STATES = {"completed", "cancelled", "archived"}

    def __init__(self, work_item_service=None, memory_service=None):
        self.work_item_service = work_item_service
        self.memory_service = memory_service

    def _work_items(self):
        if self.work_item_service is None:
            from app.services.work_items.work_item_service import WorkItemService
            service = WorkItemService()
        else:
            service = self.work_item_service
        return service.list_workflows(limit=200)

    def _goals(self):
        if self.memory_service is None:
            from app.services.memory.memory_service import MemoryService
            memory = MemoryService()
        else:
            memory = self.memory_service
        return memory.get_all().get("goals", [])

    @staticmethod
    def _parse_time(value):
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except (TypeError, ValueError):
            return None

    def list(self, project_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        limit = max(1, min(limit, 200))
        blockers: list[dict[str, Any]] = []
        workflows = self._work_items()
        for workflow in workflows:
            if project_id and workflow.get("project_id") != project_id:
                continue
            tasks = workflow.get("tasks", [])
            by_id = {
                item.get("task_id"): item
                for item in tasks if isinstance(item, dict) and item.get("task_id")
            }
            for task in by_id.values():
                status = str(task.get("status") or "").lower()
                dependencies = task.get("dependencies", [])
                unmet = [
                    dep for dep in dependencies
                    if by_id.get(dep, {}).get("status") != "completed"
                ]
                failed_dependencies = [
                    dep for dep in unmet
                    if by_id.get(dep, {}).get("status") == "failed"
                ]
                kind = None
                reason = task.get("blocker")
                if status == "failed":
                    kind = "failed_task"
                    reason = reason or "Task execution failed"
                elif status == "blocked":
                    kind = "manual_blocker" if not unmet else "dependency_blocker"
                    reason = reason or "Task is explicitly blocked"
                elif status == "pending" and unmet:
                    kind = "dependency_failure" if failed_dependencies else "dependency_wait"
                    reason = (
                        "A required dependency failed"
                        if failed_dependencies else "Required tasks are not completed"
                    )
                if kind:
                    blockers.append({
                        "id": f"{workflow.get('workflow_id')}:{task.get('task_id')}",
                        "kind": kind,
                        "severity": "critical" if failed_dependencies or status == "failed" else "high",
                        "status": status,
                        "title": task.get("title"),
                        "reason": str(reason)[:1000],
                        "workflow_id": workflow.get("workflow_id"),
                        "workflow_title": workflow.get("title"),
                        "task_id": task.get("task_id"),
                        "goal_id": workflow.get("goal_id"),
                        "project_id": workflow.get("project_id"),
                        "unmet_dependencies": unmet[:20],
                        "failed_dependencies": failed_dependencies[:20],
                        "updated_at": task.get("updated_at"),
                    })

        for goal in self._goals():
            if not isinstance(goal, dict) or goal.get("archived"):
                continue
            if project_id and goal.get("project_id") != project_id:
                continue
            if str(goal.get("status") or "").lower() in self.TERMINAL_GOAL_STATES:
                continue
            raw_blockers = goal.get("blockers", [])
            if not isinstance(raw_blockers, list):
                continue
            for index, raw in enumerate(raw_blockers[:50]):
                if isinstance(raw, dict):
                    reason = raw.get("reason") or raw.get("title") or raw.get("description") or "Goal blocker recorded"
                    status = str(raw.get("status") or "open").lower()
                    if status in {"resolved", "completed", "closed"}:
                        continue
                    item = dict(raw)
                else:
                    reason = str(raw).strip()
                    status = "open"
                    item = {}
                if not reason:
                    continue
                blockers.append({
                    **item,
                    "id": item.get("id") or f"{goal.get('goal_id')}:blocker:{index}",
                    "kind": item.get("kind") or "goal_blocker",
                    "severity": item.get("severity") or "high",
                    "status": status,
                    "title": item.get("title") or goal.get("title"),
                    "reason": str(reason)[:1000],
                    "goal_id": goal.get("goal_id"),
                    "project_id": goal.get("project_id"),
                })

        blockers.sort(key=lambda item: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(str(item.get("severity")), 4),
            str(item.get("updated_at") or ""),
            str(item.get("id") or ""),
        ))
        kinds = Counter(str(item.get("kind") or "unknown") for item in blockers)
        return {
            "success": True,
            "count": len(blockers),
            "by_kind": dict(kinds),
            "blockers": blockers[:limit],
            "project_id": project_id,
        }
