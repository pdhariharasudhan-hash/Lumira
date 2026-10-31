from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class CoreDiagnosticsService:
    """Produce a compact diagnostic snapshot from Lumira's shared services."""

    def __init__(self, health_service=None, event_service=None):
        self.health_service = health_service
        self.event_service = event_service

    def snapshot(self) -> dict[str, Any]:
        diagnostics: dict[str, Any] = {"timestamp": datetime.now(timezone.utc).isoformat()}
        try:
            if self.health_service is None:
                from app.services.system.system_health_service import SystemHealthService
                health = SystemHealthService().snapshot()
            else:
                health = self.health_service.snapshot()
            diagnostics["health"] = health
        except Exception as exc:
            diagnostics["health"] = {"success": False, "status": "degraded", "error": type(exc).__name__}

        try:
            if self.event_service is None:
                from app.services.system.core_event_log_service import CoreEventLogService
                events = CoreEventLogService().recent(20)
            else:
                events = self.event_service.recent(20)
            records = events.get("events", []) if isinstance(events, dict) else []
            diagnostics["recent_event_count"] = len(records)
            diagnostics["recent_event_types"] = sorted({str(item.get("event")) for item in records if isinstance(item, dict)})
        except Exception as exc:
            diagnostics["recent_event_error"] = type(exc).__name__

        status = diagnostics.get("health", {}).get("status", "degraded")
        diagnostics["status"] = status
        diagnostics["success"] = status == "healthy"
        return diagnostics
