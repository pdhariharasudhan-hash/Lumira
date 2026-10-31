from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CoreEventLogService:
    """Bounded durable event timeline for feature and core execution."""

    MAX_EVENTS = 2000

    def __init__(self, storage_path: str | Path = "memory/core_events.json"):
        self.storage_path = Path(storage_path)
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.storage_path.read_text(encoding="utf-8")) if self.storage_path.exists() else []
        except Exception:
            return []

    def record(self, event: str, source: str, data: dict[str, Any] | None = None,
               session_id: str | None = None, project_id: str | None = None, goal_id: str | None = None) -> dict:
        if not event or not source:
            return {"success": False, "error": "invalid_event"}
        from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
        item={"id":f"event-{datetime.now(timezone.utc).timestamp_ns()}","event":event,
              "source":source,"data":data or {},"timestamp":datetime.now(timezone.utc).isoformat(),
              "core_context":CoreRuntimeBridgeService().execution_context(
                  "core_event_record",session_id,project_id,goal_id)}
        with self._lock:
            items=self._load(); items.append(item); items=items[-self.MAX_EVENTS:]
            self.storage_path.parent.mkdir(parents=True,exist_ok=True)
            self.storage_path.write_text(json.dumps(items,indent=2),encoding="utf-8")
        return {"success": True, "event_record": item}

    def recent(self, limit: int = 50) -> dict:
        with self._lock:
            return {"success": True, "events": self._load()[-max(1,min(limit,200)):]}
