from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from typing import Any

from app.services.memory.memory_service import MemoryService
from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class NotepadValidationError(ValueError):
    pass


class NotepadService:
    """Small persistent personal notepad backed by atomic JSON writes."""

    def __init__(self, path: str = "memory/notepad.json"):
        self.path = path
        self.store = AtomicJsonStore(path)
        self._ensure_store()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _ensure_store(self) -> None:
        current = self.store.read(default=None)
        if current is None:
            if Path(self.path).exists():
                raise PersistenceIntegrityError("Notepad store is corrupt; refusing to reset it")
            self.store.write({"schema_version": 1, "notes": []})
            return
        self._validate_document(current)

    @staticmethod
    def _validate_document(document: Any) -> None:
        if not isinstance(document, dict) or document.get("schema_version") != 1:
            raise PersistenceIntegrityError("Notepad document has an unsupported schema")
        notes = document.get("notes")
        if not isinstance(notes, list):
            raise PersistenceIntegrityError("Notepad notes must be a list")
        seen: set[str] = set()
        for note in notes:
            if not isinstance(note, dict):
                raise PersistenceIntegrityError("Notepad contains a malformed note")
            note_id, title, content = note.get("note_id"), note.get("title"), note.get("content")
            if (
                not isinstance(note_id, str) or not note_id.strip() or note_id in seen
                or not isinstance(title, str) or not title.strip() or len(title) > 200
                or not isinstance(content, str) or len(content) > 20000
                or not isinstance(note.get("created_at"), str)
                or not isinstance(note.get("updated_at"), str)
            ):
                raise PersistenceIntegrityError("Notepad contains an invalid note record")
            seen.add(note_id)

    def _read(self) -> dict[str, Any]:
        document = self.store.read(default=None)
        self._validate_document(document)
        return document

    @staticmethod
    def _text(value: Any, field: str, maximum: int, allow_empty: bool = False) -> str:
        if not isinstance(value, str):
            raise NotepadValidationError(f"{field} must be text")
        value = value.strip() if field == "title" else value
        if (not allow_empty and not value.strip()) or len(value) > maximum:
            raise NotepadValidationError(f"{field} must be non-empty and at most {maximum} characters")
        return MemoryService._safe_text(value)

    def list_notes(self) -> list[dict[str, Any]]:
        notes = deepcopy(self._read()["notes"])
        notes.sort(key=lambda item: (item["updated_at"], item["note_id"]), reverse=True)
        return notes

    def create_note(self, title: str, content: str = "") -> dict[str, Any]:
        title = self._text(title, "title", 200)
        content = self._text(content, "content", 20000, allow_empty=True)
        now = self._now()
        note = {
            "note_id": uuid4().hex,
            "title": title,
            "content": content,
            "created_at": now,
            "updated_at": now,
        }
        document = self._read()
        document["notes"].append(note)
        self.store.write(document)
        return deepcopy(note)

    def update_note(self, note_id: str, *, title: str | None = None, content: str | None = None) -> dict[str, Any]:
        if not isinstance(note_id, str) or not note_id.strip():
            raise NotepadValidationError("note_id is invalid")
        document = self._read()
        for note in document["notes"]:
            if note["note_id"] != note_id:
                continue
            if title is None and content is None:
                raise NotepadValidationError("At least one field must be supplied")
            if title is not None:
                note["title"] = self._text(title, "title", 200)
            if content is not None:
                note["content"] = self._text(content, "content", 20000, allow_empty=True)
            note["updated_at"] = self._now()
            self.store.write(document)
            return deepcopy(note)
        raise KeyError(note_id)

    def delete_note(self, note_id: str) -> bool:
        if not isinstance(note_id, str) or not note_id.strip():
            raise NotepadValidationError("note_id is invalid")
        document = self._read()
        remaining = [note for note in document["notes"] if note["note_id"] != note_id]
        if len(remaining) == len(document["notes"]):
            raise KeyError(note_id)
        document["notes"] = remaining
        self.store.write(document)
        return True
