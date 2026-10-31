from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class QuickTaskService:
    """Durable personal task capture connected to Lumira core context."""

    def __init__(self, storage_path: str | Path = "memory/quick_tasks.json"):
        self.storage_path = Path(storage_path)
        self._lock = threading.RLock()

    def _load(self):
        try:
            return json.loads(self.storage_path.read_text(encoding="utf-8")) if self.storage_path.exists() else []
        except Exception:
            return []

    def _save(self, items):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(items[-1000:], indent=2), encoding="utf-8")

    def create(self, title: str, session_id=None, project_id=None, goal_id=None):
        if not isinstance(title, str) or not title.strip():
            return {"success": False, "error": "invalid_title"}
        from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
        item = {"id": f"task-{datetime.now(timezone.utc).timestamp_ns()}",
                "title": title.strip(), "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "core_context": CoreRuntimeBridgeService().execution_context(
                    "quick_task_create", session_id, project_id, goal_id)}
        with self._lock:
            items=self._load(); items.append(item); self._save(items)
        return {"success": True, "task": item}

    def list(self, status: str | None = None):
        with self._lock:
            items=self._load()
            return {"success": True, "tasks": [x for x in items if not status or x.get("status")==status]}

    def complete(self, task_id: str):
        with self._lock:
            items=self._load()
            for item in items:
                if item.get("id")==task_id:
                    item["status"]="completed"; item["completed_at"]=datetime.now(timezone.utc).isoformat(); self._save(items)
                    return {"success": True, "task": item}
        return {"success": False, "error": "task_not_found"}
