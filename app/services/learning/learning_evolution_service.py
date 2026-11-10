from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class LearningEvolutionService:
    """Persist approved skills and evidence-backed knowledge updates."""

    def __init__(self, file_path: str | Path = "data/learning_evolution.json"):
        self.store = AtomicJsonStore(Path(file_path))

    @staticmethod
    def _default() -> dict[str, Any]:
        return {"schema_version": 1, "skills": [], "knowledge_updates": []}

    def register_skill(self, name: str, evidence: list[str], approved: bool = False) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
            raise ValueError("skill name is required")
        if not isinstance(evidence, list) or not evidence or any(
            not isinstance(item, str) or not item.strip() for item in evidence
        ):
            raise ValueError("skill evidence must be a non-empty list of strings")
        if not isinstance(approved, bool):
            raise ValueError("approved must be boolean")
        record = {
            "skill_id": str(uuid4()),
            "name": name.strip(),
            "evidence": list(dict.fromkeys(item.strip() for item in evidence)),
            "approved": approved,
            "created_at": datetime.now(UTC).isoformat(),
        }

        def append(data):
            if any(item.get("name") == record["name"] for item in data["skills"]):
                raise ValueError("skill already exists")
            data["skills"].append(record)
            return record

        try:
            return self.store.update(append, self._default())
        except PersistenceIntegrityError as exc:
            raise ValueError("learning registry integrity failure") from exc

    def improve_knowledge(self, topic: str, observation: str, source: str, approved: bool = False) -> dict[str, Any]:
        values = (topic, observation, source)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("topic, observation, and source are required")
        if not isinstance(approved, bool):
            raise ValueError("approved must be boolean")
        record = {
            "update_id": str(uuid4()),
            "topic": topic.strip(),
            "observation": observation.strip(),
            "source": source.strip(),
            "approved": approved,
            "created_at": datetime.now(UTC).isoformat(),
        }

        def append(data):
            data["knowledge_updates"].append(record)
            return record

        try:
            return self.store.update(append, self._default())
        except PersistenceIntegrityError as exc:
            raise ValueError("learning registry integrity failure") from exc
