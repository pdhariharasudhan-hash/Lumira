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
        self.store.update(self._validate_document, {"schema_version": 1, "items": []})

    @classmethod
    def _validate_document(cls, data):
        if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("items"), list):
            raise PersistenceIntegrityError("personal todo store has an invalid schema")
        seen = set()
        for item in data["items"]:
            if not isinstance(item, dict):
                raise PersistenceIntegrityError("personal todo store contains an invalid task record")
            task_id = item.get("task_id")
            title = item.get("title")
            status = item.get("status")
            priority = item.get("priority")
            progress = item.get("progress")
            if not isinstance(task_id, str) or not task_id or len(task_id) > 128 or task_id in seen:
                raise PersistenceIntegrityError("personal todo task identity is invalid")
            if not isinstance(title, str) or not title.strip() or len(title) > 500:
                raise PersistenceIntegrityError("personal todo title is invalid")
            if not isinstance(status, str) or status not in cls.STATUSES:
                raise PersistenceIntegrityError("personal todo status is invalid")
            if not isinstance(priority, str) or priority not in cls.PRIORITIES:
                raise PersistenceIntegrityError("personal todo priority is invalid")
            if isinstance(progress, bool) or not isinstance(progress, int) or not 0 <= progress <= 100:
                raise PersistenceIntegrityError("personal todo progress is invalid")
            for field, maximum in (("project_id", 128), ("blocker", 2000), ("created_at", 40)):
                value = item.get(field)
                if field == "created_at":
                    if not isinstance(value, str) or not value or len(value) > maximum:
                        raise PersistenceIntegrityError("personal todo timestamp is invalid")
                elif value is not None and (not isinstance(value, str) or len(value) > maximum):
                    raise PersistenceIntegrityError(f"personal todo {field} is invalid")
            seen.add(task_id)
        return data

    def _read(self):
        return self._validate_document(self.store.read({"schema_version": 1, "items": []}))

    def create(self, title: str, priority: str = "medium", project_id: str | None = None, blocker: str | None = None):
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 500:
            raise ValueError("title must contain 1 to 500 characters")
        if not isinstance(priority, str) or priority not in self.PRIORITIES: raise ValueError("unsupported priority")
        item = {"task_id": str(uuid4()), "title": title.strip(), "priority": priority, "project_id": project_id, "blocker": blocker, "status": "blocked" if blocker else "pending", "progress": 0, "created_at": datetime.now(UTC).isoformat()}
        def append(data):
            self._validate_document(data)
            data["items"].append(item)
            return dict(item)
        return self.store.update(append, {"schema_version": 1, "items": []})

    def update_progress(self, task_id: str, progress: int):
        if isinstance(progress, bool) or not isinstance(progress, int) or not 0 <= progress <= 100: raise ValueError("progress must be between 0 and 100")
        result = {}
        def update(data):
            self._validate_document(data)
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
