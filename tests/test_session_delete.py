
from fastapi.testclient import TestClient

from app.main import app
from app.services.sessions.session_manager_service import SessionManagerService


def test_delete_session_route_removes_conversation_from_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SessionManagerService()
    session = manager.create_session()
    manager.append_message(session["session_id"], "user", "delete this conversation")

    response = TestClient(app).delete(f"/sessions/{session['session_id']}")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "session_id": session["session_id"],
        "deleted": True,
    }
    assert SessionManagerService().get_session(session["session_id"]) is None


def test_delete_session_route_returns_404_for_unknown_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).delete("/sessions/not-a-real-session")
    assert response.status_code == 404
