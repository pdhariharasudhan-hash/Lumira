from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class GoalInsightsService:
    """Read-only goal portfolio insights backed by Lumira's existing memory store."""

    def __init__(self, memory_service=None):
        self.memory_service = memory_service

    def summary(self, project_id: str | None = None) -> dict[str, Any]:
        if self.memory_service is None:
            from app.services.memory.memory_service import MemoryService
            memory = MemoryService()
        else:
            memory = self.memory_service
        goals = memory.get_all().get("goals", [])
        if project_id:
            goals = [g for g in goals if isinstance(g, dict) and g.get("project_id") == project_id]
        counts: dict[str, int] = {}
        progress_values = []
        for goal in goals:
            if not isinstance(goal, dict):
                continue
            status = str(goal.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
            progress = goal.get("progress")
            if isinstance(progress, (int, float)) and not isinstance(progress, bool):
                progress_values.append(float(progress))
        total = sum(counts.values())
        return {
            "success": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_goals": total,
            "status_counts": counts,
            "average_progress": round(sum(progress_values) / len(progress_values), 2) if progress_values else 0.0,
        }
