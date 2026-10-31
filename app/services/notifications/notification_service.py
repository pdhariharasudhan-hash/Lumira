from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class NotificationService:
    """Durable in-app notification inbox tied to Lumira execution context."""

    MAX_ITEMS = 500

    def __init__(self, storage_path: str | Path = "memory/notifications.json"):
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
        self.storage_path.write_text(json.dumps(items[-self.MAX_ITEMS:], indent=2), encoding="utf-8")

    def create(self, message: str, level: str = "info",
               session_id: str | None = None, project_id: str | None = None,
               goal_id: str | None = None) -> dict[str, Any]:
        if not isinstance(message, str) or not message.strip():
            return {"success": False, "error": "invalid_message"}
        if level not in {"info", "success", "warning", "error"}:
            return {"success": False, "error": "invalid_level"}

        from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
        context = CoreRuntimeBridgeService().execution_context(
            "notification_create", session_id, project_id, goal_id
        )
        item = {
            "id": f"notification-{datetime.now(timezone.utc).timestamp_ns()}",
            "message": message.strip(),
            "level": level,
            "status": "unread",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "core_context": context,
        }
        with self._lock:
            items = self._load()
            items.append(item)
            self._save(items)
        return {"success": True, "notification": item}

    def list(self, unread_only: bool = False) -> dict[str, Any]:
        with self._lock:
            items = self._load()
            if unread_only:
                items = [item for item in items if item.get("status") == "unread"]
            return {"success": True, "notifications": items}

    def mark_read(self, notification_id: str) -> dict[str, Any]:
        with self._lock:
            items = self._load()
            for item in items:
                if item.get("id") == notification_id:
                    item["status"] = "read"
                    item["read_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(items)
                    return {"success": True, "notification": item}
        return {"success": False, "error": "notification_not_found"}
