from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class PersonalLibraryService:
    """Private catalog for the user's documents, notes, references and useful links."""

    TYPES = {"document", "note", "idea", "research", "reference", "link", "generated_content"}
    MAX_ITEMS = 5000

    def __init__(self, path: str | Path = "memory/personal_library.json"):
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        if not self.path.exists():
            self.store.write({"schema_version": 1, "items": []})

    @classmethod
    def _validate(cls, document):
        if not isinstance(document, dict) or document.get("schema_version") != 1 or not isinstance(document.get("items"), list):
            raise PersistenceIntegrityError("personal library has an invalid schema")
        if len(document["items"]) > cls.MAX_ITEMS:
            raise PersistenceIntegrityError("personal library exceeds retention limit")
        for item in document["items"]:
            if not isinstance(item, dict) or not isinstance(item.get("item_id"), str) or not isinstance(item.get("title"), str):
                raise PersistenceIntegrityError("personal library contains an invalid item")
        return document

    @staticmethod
    def _clean(value, name, limit):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise ValueError(f"{name} must contain 1 to {limit} characters")
        return value.strip()

    def add(self, title: str, item_type: str, content: str = "", project_id: str | None = None, source: str | None = None) -> dict:
        title = self._clean(title, "title", 300)
        if item_type not in self.TYPES:
            raise ValueError("unsupported library item type")
        if not isinstance(content, str) or len(content) > 100_000:
            raise ValueError("content must be at most 100000 characters")
        if project_id is not None:
            project_id = self._clean(project_id, "project_id", 200)
        if source is not None:
            source = self._clean(source, "source", 2000)
        item = {
            "item_id": str(uuid4()), "title": title, "type": item_type, "content": content,
            "project_id": project_id, "source": source, "created_at": datetime.now(UTC).isoformat(),
        }
        def append(document):
            self._validate(document)
            document["items"].append(item)
            return item
        return self.store.update(append, {"schema_version": 1, "items": []})

    def list(self, item_type: str | None = None, project_id: str | None = None, limit: int = 100) -> list[dict]:
        if item_type is not None and item_type not in self.TYPES:
            raise ValueError("unsupported library item type")
        if not 0 <= limit <= 200:
            raise ValueError("limit must be between 0 and 200")
        document = self._validate(self.store.read({"schema_version": 1, "items": []}))
        items = [dict(item) for item in document["items"] if (item_type is None or item.get("type") == item_type) and (project_id is None or item.get("project_id") == project_id)]
        return list(reversed(items[-limit:])) if limit else []

    def search(self, query: str, limit: int = 50) -> list[dict]:
        query = self._clean(query, "query", 500).casefold()
        return [item for item in self.list(limit=200) if query in (item.get("title", "") + "\n" + item.get("content", "")).casefold()][:limit]
