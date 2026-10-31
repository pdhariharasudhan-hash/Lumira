from __future__ import annotations

from typing import Any


class NotificationInsightsService:
    """Read-only notification activity summary."""

    def __init__(self, notification_service=None):
        self.notification_service = notification_service

    def summary(self) -> dict[str, Any]:
        if self.notification_service is None:
            from app.services.notifications.notification_service import NotificationService
            service = NotificationService()
        else:
            service = self.notification_service
        result = service.list()
        items = result.get("notifications", []) if isinstance(result, dict) else []
        levels: dict[str, int] = {}
        unread = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            level = str(item.get("level", "info"))
            levels[level] = levels.get(level, 0) + 1
            unread += item.get("status") == "unread"
        return {"success": True, "total": len(items), "unread": unread, "level_counts": levels}
