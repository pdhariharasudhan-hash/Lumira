from fastapi.testclient import TestClient

from app.main import app


def test_app_lifespan_starts_and_stops_application_lifecycle_manager():
    with TestClient(app) as client:
        lifecycle = app.state.lifecycle_manager
        assert lifecycle.state == "running"
        assert lifecycle.snapshot()["started_hooks"] == ["optional_providers"]
        response = client.get("/health")
        assert response.status_code == 200
        assert lifecycle.snapshot()["active_work"] == 0
    assert lifecycle.state == "stopped"
    assert lifecycle.snapshot()["started_hooks"] == []
