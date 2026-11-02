from __future__ import annotations

from typing import Any

from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService


class CoreRequestBridgeService:
    """Single request-level bridge used by every FastAPI route."""

    CONTEXT_KEYS = ("session_id", "project_id", "goal_id")

    def build(self, request: Any) -> dict:
        query = getattr(request, "query_params", {})
        headers = getattr(request, "headers", {})

        values = {}
        for key in self.CONTEXT_KEYS:
            value = query.get(key) if hasattr(query, "get") else None
            if not value and hasattr(headers, "get"):
                value = headers.get(f"x-lumira-{key.replace('_', '-')}")
            values[key] = value or None

        operation = getattr(getattr(request, "url", None), "path", "request")
        return CoreRuntimeBridgeService().execution_context(
            operation=operation,
            session_id=values["session_id"],
            project_id=values["project_id"],
            goal_id=values["goal_id"],
        )
