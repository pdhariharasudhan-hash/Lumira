from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReminderService:
    """Small persistent reminder engine with explicit main-core context."""

    def __init__(self, storage_path: str | Path = "memory/reminders.json"):
        self.storage_path = Path(storage_path)
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        if not self.storage_path.exists():
            return []
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def create(self, message: str, due_at: str, session_id: str | None = None,
               project_id: str | None = None, goal_id: str | None = None) -> dict:
        if not isinstance(message, str) or not message.strip():
            return {"success": False, "error": "invalid_message"}
        try:
            due = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return {"success": False, "error": "invalid_due_at"}

        from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
        core_context = CoreRuntimeBridgeService().execution_context(
            "reminder_create", session_id, project_id, goal_id
        )
        item = {
            "id": f"reminder-{datetime.now(timezone.utc).timestamp_ns()}",
            "message": message.strip(),
            "due_at": due.astimezone(timezone.utc).isoformat(),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "core_context": core_context,
        }
        with self._lock:
            items = self._load()
            items.append(item)
            self._save(items)
        return {"success": True, "reminder": item}

    def due(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        triggered = []
        with self._lock:
            items = self._load()
            for item in items:
                due_at = datetime.fromisoformat(item["due_at"])
                if item.get("status") == "pending" and due_at <= now:
                    item["status"] = "due"
                    item["triggered_at"] = now.isoformat()
                    triggered.append(item)
            self._save(items)
        return {"success": True, "reminders": triggered}

    def list(self) -> dict:
        with self._lock:
            return {"success": True, "reminders": self._load()}
