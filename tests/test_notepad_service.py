import json

import pytest

from app.services.notepad_service import NotepadService, NotepadValidationError
from app.services.persistence.atomic_json_store import PersistenceIntegrityError


def test_notepad_persists_create_update_and_delete(tmp_path):
    path = tmp_path / "notepad.json"
    service = NotepadService(str(path))
    note = service.create_note("Quick Note", "first version")

    reloaded = NotepadService(str(path))
    assert reloaded.list_notes()[0]["note_id"] == note["note_id"]
    updated = reloaded.update_note(note["note_id"], content="second version")
    assert updated["content"] == "second version"
    assert reloaded.delete_note(note["note_id"]) is True
    assert reloaded.list_notes() == []


def test_notepad_bounds_fields_and_requires_an_update(tmp_path):
    service = NotepadService(str(tmp_path / "notepad.json"))
    with pytest.raises(NotepadValidationError):
        service.create_note(" " * 201, "content")
    note = service.create_note("Quick Note", "")
    with pytest.raises(NotepadValidationError, match="At least one field"):
        service.update_note(note["note_id"])


def test_notepad_redacts_secret_like_content(tmp_path):
    service = NotepadService(str(tmp_path / "notepad.json"))
    note = service.create_note("Quick Note", "api_key=super-secret-value")
    assert "super-secret-value" not in note["content"]
    persisted = json.loads((tmp_path / "notepad.json").read_text(encoding="utf-8"))
    assert "super-secret-value" not in json.dumps(persisted)


def test_notepad_does_not_overwrite_corrupt_storage(tmp_path):
    path = tmp_path / "notepad.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError):
        NotepadService(str(path))
    assert path.read_text(encoding="utf-8") == "{broken"
