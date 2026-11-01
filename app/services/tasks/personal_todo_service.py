from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class PersonalTodoService:
    STATUSES = {"pending", "in_progress", "blocked", "completed", "paused"}
    PRIORITIES = {"low", "medium", "high", "critical"}

    def __init__(self, path: str | Path = "memory/personal_todos.json"):
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        if not self.path.exists(): self.store.write({"schema_version": 1, "items": []})

    def _read(self):
        data = self.store.read({"schema_version": 1, "items": []})
        if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("items"), list):
            raise PersistenceIntegrityError("personal todo store has an invalid schema")
        return data

    def create(self, title: str, priority: str = "medium", project_id: str | None = None, blocker: str | None = None):
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 500:
            raise ValueError("title must contain 1 to 500 characters")
        if priority not in self.PRIORITIES: raise ValueError("unsupported priority")
        item = {"task_id": str(uuid4()), "title": title.strip(), "priority": priority, "project_id": project_id, "blocker": blocker, "status": "blocked" if blocker else "pending", "progress": 0, "created_at": datetime.now(UTC).isoformat()}
        def append(data): self._read(); data["items"].append(item); return item
        return self.store.update(append, {"schema_version": 1, "items": []})

    def update_progress(self, task_id: str, progress: int):
        if not isinstance(progress, int) or not 0 <= progress <= 100: raise ValueError("progress must be between 0 and 100")
        result = {}
        def update(data):
            for item in data["items"]:
                if item.get("task_id") == task_id:
                    item["progress"] = progress
                    item["status"] = "completed" if progress == 100 else ("blocked" if item.get("blocker") else "in_progress")
                    result.update(item); return result
            raise KeyError("task not found")
        return self.store.update(update, {"schema_version": 1, "items": []})

    def list(self, status: str | None = None):
        if status is not None and status not in self.STATUSES: raise ValueError("unsupported status")
        return [dict(item) for item in reversed(self._read()["items"]) if status is None or item.get("status") == status]
