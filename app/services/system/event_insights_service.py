from __future__ import annotations

from collections import Counter
from typing import Any


class EventInsightsService:
    """Analyze the existing bounded core event timeline."""

    def __init__(self, event_service=None):
        self.event_service = event_service

    def summary(self, limit: int = 200) -> dict[str, Any]:
        if self.event_service is None:
            from app.services.system.core_event_log_service import CoreEventLogService
            service = CoreEventLogService()
        else:
            service = self.event_service
        events = service.recent(max(1, min(limit, 500))).get("events", [])
        sources = Counter(str(item.get("source", "unknown")) for item in events if isinstance(item, dict))
        types = Counter(str(item.get("event", "unknown")) for item in events if isinstance(item, dict))
        failures = sum(1 for item in events if isinstance(item, dict) and "failed" in str(item.get("event", "")).lower())
        return {"success": True, "event_count": len(events), "failure_events": failures,
                "source_counts": dict(sources), "event_counts": dict(types)}
