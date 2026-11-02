from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class GoalAttentionService:
    """Identify goals that need attention without mutating durable goal state."""

    def __init__(self, memory_service=None):
        self.memory_service = memory_service

    def attention(self, project_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        if self.memory_service is None:
            from app.services.memory.memory_service import MemoryService
            memory = MemoryService()
        else:
            memory = self.memory_service
        now = datetime.now(timezone.utc)
        findings = []
        for goal in memory.get_all().get("goals", []):
            if not isinstance(goal, dict) or goal.get("archived"):
                continue
            if project_id and goal.get("project_id") != project_id:
                continue
            reasons = []
            deadline = goal.get("deadline")
            if isinstance(deadline, str) and deadline:
                try:
                    parsed = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    if parsed < now and goal.get("status") not in {"completed", "cancelled"}:
                        reasons.append("deadline_overdue")
                except ValueError:
                    reasons.append("deadline_invalid")
            blockers = goal.get("blockers", [])
            if isinstance(blockers, list) and blockers:
                reasons.append("has_blockers")
            if reasons:
                findings.append({"goal_id": goal.get("goal_id"), "title": goal.get("title"),
                                 "status": goal.get("status"), "reasons": reasons,
                                 "progress": goal.get("progress", 0)})
        return {"success": True, "count": len(findings), "goals": findings[:max(1, min(limit, 200))]}
