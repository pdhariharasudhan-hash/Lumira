from fastapi.testclient import TestClient

from app.main import app


def test_brain_execute_requires_explicit_capability_fields():
    response = TestClient(app).post(
        "/brain/execute",
        json={"message": "plan a project", "capability": ""},
    )

    assert response.status_code == 422


def test_brain_execute_returns_structured_failed_result_for_unverified_execution(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).post(
        "/brain/execute",
        json={
            "message": "create a project",
            "capability": "code_generation",
            "payload": {"idea": "create a harmless project"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["status"] == "error"
    assert body["data"]["success"] is False
    assert body["data"]["error"] == "Verification rejected execution"
