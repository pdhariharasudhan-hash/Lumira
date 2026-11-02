from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ActionPriorityService:
    """Deterministic task ranking using urgency, importance, blockers and dependencies.

    Scores are explainable and bounded to 0..100. Missing evidence receives a
    neutral score rather than being guessed.
    """

    def _urgency(self, action: dict[str, Any]) -> tuple[int, list[str]]:
        reasons: list[str] = []
        due = action.get("due_at") or action.get("deadline")
        if isinstance(due, str) and due:
            try:
                value = datetime.fromisoformat(due.replace("Z", "+00:00"))
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                hours = (value - datetime.now(timezone.utc)).total_seconds() / 3600
                if hours < 0:
                    reasons.append("deadline_overdue")
                    return 100, reasons
                if hours <= 24:
                    reasons.append("deadline_within_24_hours")
                    return 90, reasons
                if hours <= 72:
                    reasons.append("deadline_within_72_hours")
                    return 75, reasons
                if hours <= 168:
                    reasons.append("deadline_within_7_days")
                    return 60, reasons
            except (TypeError, ValueError, OverflowError):
                reasons.append("deadline_unparseable")
        priority = str(action.get("priority", "")).lower()
        if priority in {"critical", "urgent"}:
            reasons.append("explicit_critical_priority")
            return 100, reasons
        if priority == "high":
            reasons.append("explicit_high_priority")
            return 80, reasons
        if priority == "low":
            reasons.append("explicit_low_priority")
            return 20, reasons
        return 40, reasons

    def rank(self, actions, attention=None, blockers=None, limit: int = 100):
        attention = attention or []
        blockers = blockers or []
        urgent_goals = {
            item.get("goal_id") for item in attention
            if isinstance(item, dict) and item.get("goal_id")
        }
        blocked_goal_ids = {
            item.get("goal_id") for item in blockers
            if isinstance(item, dict) and item.get("goal_id")
        }
        blocker_by_task = {
            item.get("task_id"): item for item in blockers
            if isinstance(item, dict) and item.get("task_id")
        }
        ranked = []
        for original in actions or []:
            if not isinstance(original, dict):
                continue
            item = dict(original)
            reasons: list[str] = []
            urgency, urgency_reasons = self._urgency(item)
            reasons.extend(urgency_reasons)
            importance = 80 if item.get("goal_id") in urgent_goals else 40
            if item.get("goal_id") in urgent_goals:
                reasons.append("linked_goal_needs_attention")
            impact = 80 if item.get("goal_id") in blocked_goal_ids else 30
            if item.get("goal_id") in blocked_goal_ids:
                reasons.append("linked_goal_has_blockers")
            blocker = blocker_by_task.get(item.get("task_id"))
            blocker_penalty = 35 if blocker or item.get("status") == "blocked" else 0
            if blocker_penalty:
                reasons.append("action_is_blocked_not_executable")
            progress_penalty = 10 if item.get("status") == "in_progress" else 0
            if progress_penalty:
                reasons.append("already_in_progress")
            score = round(
                urgency * 0.35 + importance * 0.30 + impact * 0.25
                + max(0, 50 - blocker_penalty - progress_penalty) * 0.10
            )
            item["priority_score"] = max(0, min(100, score))
            item["priority_reasons"] = reasons or ["default_ranked_from_available_context"]
            item["is_executable"] = not bool(blocker) and item.get("status") != "blocked"
            ranked.append(item)
        ranked.sort(
            key=lambda value: (
                -value["priority_score"],
                str(value.get("deadline") or value.get("due_at") or "9999"),
                str(value.get("task_id") or ""),
            )
        )
        bounded = max(1, min(int(limit), 200))
        return {"success": True, "count": len(ranked), "actions": ranked[:bounded]}
