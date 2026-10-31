from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class SystemHealthService:
    """Aggregate bounded health information from Lumira's durable subsystems."""

    def __init__(self, event_service=None, notification_service=None):
        self.event_service = event_service
        self.notification_service = notification_service

    def snapshot(self) -> dict[str, Any]:
        checks = {}
        try:
            events = self.event_service
            if events is None:
                from app.services.system.core_event_log_service import CoreEventLogService
                events = CoreEventLogService()
            result = events.recent(1)
            checks["core_events"] = {"status": "healthy", "count": len(result.get("events", []))}
        except Exception as exc:
            checks["core_events"] = {"status": "degraded", "error": type(exc).__name__}

        try:
            notifications = self.notification_service
            if notifications is None:
                from app.services.notifications.notification_service import NotificationService
                notifications = NotificationService()
            result = notifications.list(unread_only=True)
            checks["notifications"] = {"status": "healthy", "unread": len(result.get("notifications", []))}
        except Exception as exc:
            checks["notifications"] = {"status": "degraded", "error": type(exc).__name__}

        overall = "healthy" if all(v["status"] == "healthy" for v in checks.values()) else "degraded"
        return {"success": True, "status": overall,
                "timestamp": datetime.now(timezone.utc).isoformat(), "checks": checks}
