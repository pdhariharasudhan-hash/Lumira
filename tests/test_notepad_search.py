from app.services.notepad_service import NotepadService


def test_search_notes_matches_title_and_content(tmp_path):
    service = NotepadService(str(tmp_path / "notes.json"))
    service.create_note("Robot project", "Use ESP32 and sensors")
    service.create_note("Study", "Physics revision")
    results = service.search_notes("ESP32")
    assert len(results) == 1
    assert results[0]["title"] == "Robot project"


def test_search_notes_rejects_invalid_limit(tmp_path):
    service = NotepadService(str(tmp_path / "notes.json"))
    try:
        service.search_notes("robot", 0)
        assert False
    except ValueError:
        assert True
