from fastapi.testclient import TestClient

from app.main import app


def test_brain_route_builds_valid_response():
    client = TestClient(app)
    response = client.post("/brain", json={"input": "Build a FastAPI expense API with authentication"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["stage"] in {"complete", "builder", "validate"}


def test_command_route_parses_request():
    client = TestClient(app)
    response = client.post("/command", json={"input": "Build a FastAPI expense API with authentication"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["parsed"]["success"] is True
