from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore


class TextIdeaCaptureService:
    CATEGORIES = {"general", "project", "electronics", "robotics", "business", "software", "research"}

    def __init__(self, path: str | Path = "memory/text_ideas.json"):
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        if not self.path.exists():
            self.store.write({"schema_version": 1, "ideas": []})

    @staticmethod
    def _clean(value: str, name: str, limit: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise ValueError(f"{name} must contain 1 to {limit} characters")
        return value.strip()

    def capture(self, text: str, title: str | None = None, category: str = "general", project_id: str | None = None) -> dict:
        text = self._clean(text, "text", 20_000)
        if category not in self.CATEGORIES:
            raise ValueError("unsupported idea category")
        title = self._clean(title, "title", 300) if title else text[:120]
        project_id = self._clean(project_id, "project_id", 200) if project_id else None
        idea = {
            "idea_id": str(uuid4()), "title": title, "raw_text": text,
            "category": category, "project_id": project_id,
            "status": "captured", "created_at": datetime.now(UTC).isoformat(),
        }
        def update(data):
            if not isinstance(data, dict) or not isinstance(data.get("ideas"), list):
                raise ValueError("idea store has invalid schema")
            data["ideas"].append(idea)
            return idea
        return self.store.update(update, {"schema_version": 1, "ideas": []})

    def list(self, query: str | None = None, project_id: str | None = None, limit: int = 100) -> list[dict]:
        if not 0 <= limit <= 200:
            raise ValueError("limit must be between 0 and 200")
        data = self.store.read({"schema_version": 1, "ideas": []})
        items = list(reversed(data.get("ideas", [])))
        if project_id:
            items = [x for x in items if x.get("project_id") == project_id]
        if query:
            q = self._clean(query, "query", 500).casefold()
            items = [x for x in items if q in (x.get("title", "") + "\n" + x.get("raw_text", "")).casefold()]
        return [dict(x) for x in items[:limit]]
