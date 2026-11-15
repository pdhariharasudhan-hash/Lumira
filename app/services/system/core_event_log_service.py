"""Atomic, bounded core event history with strict integrity and privacy controls."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.sessions.session_manager_service import redact_sensitive_value


class CoreEventLogService:
    """Durable timeline for core and feature execution events."""

    MAX_EVENTS = 2000
    MAX_EVENT_NAME = 128
    MAX_SOURCE = 128
    MAX_DATA_BYTES = 32 * 1024

    def __init__(self, storage_path: str | Path = "memory/core_events.json"):
        self.storage_path = Path(storage_path)
        self.store = AtomicJsonStore(self.storage_path)
        self.store.read_or_create([])

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _validate(cls, items: Any) -> list[dict]:
        if not isinstance(items, list) or len(items) > cls.MAX_EVENTS:
            raise PersistenceIntegrityError("core event history has an invalid shape")
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                raise PersistenceIntegrityError("core event history contains an invalid record")
            event_id = item.get("id")
            if not isinstance(event_id, str) or not event_id or event_id in seen:
                raise PersistenceIntegrityError("core event history contains duplicate or invalid IDs")
            seen.add(event_id)
            if (
                not isinstance(item.get("event"), str)
                or not item["event"].strip()
                or len(item["event"]) > cls.MAX_EVENT_NAME
                or not isinstance(item.get("source"), str)
                or not item["source"].strip()
                or len(item["source"]) > cls.MAX_SOURCE
                or not isinstance(item.get("data"), dict)
            ):
                raise PersistenceIntegrityError("core event record fields are invalid")
        return items

    def record(
        self,
        event: str,
        source: str,
        data: dict[str, Any] | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        goal_id: str | None = None,
    ) -> dict:
        if not isinstance(event, str) or not event.strip() or len(event) > self.MAX_EVENT_NAME:
            return {"success": False, "error": "invalid_event"}
        if not isinstance(source, str) or not source.strip() or len(source) > self.MAX_SOURCE:
            return {"success": False, "error": "invalid_source"}
        if data is not None and not isinstance(data, dict):
            return {"success": False, "error": "invalid_event_data"}
        try:
            safe_data = redact_sensitive_value(data or {})
            encoded = json.dumps(safe_data, ensure_ascii=False, allow_nan=False)
            if len(encoded.encode("utf-8")) > self.MAX_DATA_BYTES:
                return {"success": False, "error": "event_data_too_large"}
        except (TypeError, ValueError, RecursionError):
            return {"success": False, "error": "event_data_not_json"}

        try:
            from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
            core_context = CoreRuntimeBridgeService().execution_context(
                "core_event_record", session_id, project_id, goal_id
            )
        except Exception:
            core_context = {"success": False, "error": "core_context_unavailable"}
        item = {
            "id": f"event-{uuid4()}",
            "event": event.strip(),
            "source": source.strip(),
            "data": safe_data,
            "timestamp": self._now(),
            "core_context": core_context,
        }

        def append(items):
            records = self._validate(items)
            records.append(item)
            del records[:-self.MAX_EVENTS]
            return len(records)

        try:
            self.store.update(append, default=[])
        except Exception:
            return {"success": False, "error": "event_persistence_failed"}
        return {"success": True, "event_record": item}

    def search(self, event: str | None = None, source: str | None = None, limit: int = 100) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            return {"success": False, "error": "invalid_limit", "events": [], "count": 0}
        try:
            items = list(self._validate(self.store.read(default=[])))
        except Exception:
            return {"success": False, "error": "event_store_unavailable", "events": [], "count": 0}
        if event is not None:
            if not isinstance(event, str) or not event.strip():
                return {"success": False, "error": "invalid_event_filter", "events": [], "count": 0}
            needle = event.lower()
            items = [item for item in items if needle in item["event"].lower()]
        if source is not None:
            if not isinstance(source, str) or not source.strip():
                return {"success": False, "error": "invalid_source_filter", "events": [], "count": 0}
            needle = source.lower()
            items = [item for item in items if needle in item["source"].lower()]
        return {"success": True, "events": items[-limit:], "count": len(items)}

    def recent(self, limit: int = 50) -> dict:
        result = self.search(limit=max(1, min(limit, 200)))
        if result.get("success") is not True:
            return result
        return {"success": True, "events": result["events"]}
