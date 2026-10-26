from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["services"]["validate"] is True
    assert set(payload["providers"]) == {
        "summarization",
        "transcription",
        "speech_synthesis",
        "image_generation",
        "image_understanding",
        "research",
        "wake_word",
    }
    assert all(
        isinstance(provider["registered"], bool)
        for provider in payload["providers"].values()
    )
    assert payload["security"]["project_terminal_execution"] == "disabled"
    assert payload["security"]["sandbox_verification"] == "not_implemented"
