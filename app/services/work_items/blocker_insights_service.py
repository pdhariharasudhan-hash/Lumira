from __future__ import annotations

from collections import Counter
from typing import Any


class BlockerInsightsService:
    """Turn the existing blocker queue into deterministic actionable insights."""

    def __init__(self, blocker_service):
        self.blocker_service = blocker_service

    def summary(self, project_id=None):
        result = self.blocker_service.list(project_id=project_id, limit=200)
        items = result.get("blockers", []) if isinstance(result, dict) else []
        kinds = Counter()
        severities = Counter()
        by_goal = Counter()
        by_workflow = Counter()
        enriched = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            kind = str(item.get("kind") or item.get("type") or "unknown")
            dependency_failure = bool(
                item.get("dependency_failure")
                or item.get("failed_dependencies")
                or kind in {"dependency_failure", "dependency_blocker"}
            )
            status = str(item.get("status") or "").lower()
            severity = (
                "critical" if dependency_failure or status == "failed"
                else "high" if kind in {"manual", "explicit", "external", "manual_blocker", "goal_blocker"}
                else "medium"
            )
            item["severity"] = severity
            item["recommended_action"] = (
                "inspect_failed_dependency_and_requeue_only_after_resolution"
                if dependency_failure else
                "resolve_recorded_blocker_before_execution"
            )
            kinds[kind] += 1
            severities[severity] += 1
            if item.get("goal_id"):
                by_goal[str(item["goal_id"])] += 1
            if item.get("workflow_id"):
                by_workflow[str(item["workflow_id"])] += 1
            enriched.append(item)
        enriched.sort(
            key=lambda item: (
                {"critical": 0, "high": 1, "medium": 2}.get(item["severity"], 3),
                str(item.get("created_at") or item.get("updated_at") or ""),
            )
        )
        return {
            "success": True,
            "total": len(enriched),
            "by_kind": dict(kinds),
            "by_severity": dict(severities),
            "affected_goals": [{"goal_id": key, "count": value} for key, value in by_goal.most_common(20)],
            "affected_workflows": [{"workflow_id": key, "count": value} for key, value in by_workflow.most_common(20)],
            "blockers": enriched[:200],
        }
