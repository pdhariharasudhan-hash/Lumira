from fastapi.testclient import TestClient

from app.main import app


def test_ai_mode_routes_expose_separate_cloud_consent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    current = client.get("/ai-mode")
    assert current.status_code == 200
    assert current.json()["mode"] == "hybrid"
    assert current.json()["cloud_enabled"] is False
    assert current.json()["external_providers_allowed"] is False

    enabled = client.put("/ai-mode/cloud", json={"cloud_enabled": True})
    assert enabled.status_code == 200
    assert enabled.json()["cloud_enabled"] is True
    assert enabled.json()["external_providers_allowed"] is True

    offline = client.put("/ai-mode", json={"mode": "offline"})
    assert offline.status_code == 200
    assert offline.json()["cloud_enabled"] is True
    assert offline.json()["external_providers_allowed"] is False

    disabled = client.put("/ai-mode/cloud", json={"cloud_enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["external_providers_allowed"] is False


def test_ai_mode_route_rejects_non_boolean_cloud_consent():
    response = TestClient(app).put("/ai-mode/cloud", json={"cloud_enabled": "true"})
    assert response.status_code == 422
