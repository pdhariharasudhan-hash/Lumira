from fastapi.testclient import TestClient

from app.main import app
from app.routes import health as health_route
from app.services.providers.provider_registry import ProviderRegistry


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
        "video_generation",
        "image_understanding",
        "research",
        "wake_word",
        "device_transport",
    }
    assert all(
        isinstance(provider["registered"], bool)
        for provider in payload["providers"].values()
    )
    assert payload["security"]["project_terminal_execution"] == "disabled"
    assert payload["security"]["sandbox_verification"] == "not_implemented"



def test_provider_status_distinguishes_enabled_but_unregistered_without_exposing_secrets(monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "_providers", {})
    monkeypatch.setenv("LUMIRA_OLLAMA_VISION_ENABLED", "true")
    monkeypatch.setenv("LUMIRA_VISION_API_KEY", "do-not-return-this-secret")
    monkeypatch.setenv("LUMIRA_VISION_BASE_URL", "https://private.example.invalid/v1")

    payload = health_route.provider_status()

    vision = payload["providers"]["image_understanding"]
    assert vision["configured"] is True
    assert vision["registered"] is False
    assert "image_understanding" in payload["configured_but_unregistered"]
    serialized = str(payload)
    assert "do-not-return-this-secret" not in serialized
    assert "private.example.invalid" not in serialized


def test_provider_status_reports_local_registration_without_claiming_reachability(monkeypatch):
    class OllamaVisionProvider:
        model_name = "moondream"
        base_url = "http://127.0.0.1:11434"

    monkeypatch.setattr(ProviderRegistry, "_providers", {})
    monkeypatch.setenv("LUMIRA_OLLAMA_VISION_ENABLED", "1")
    ProviderRegistry.register("image_understanding", OllamaVisionProvider())

    try:
        payload = health_route.provider_status()
        vision = payload["providers"]["image_understanding"]
        assert vision["registered"] is True
        assert vision["configured"] is True
        assert vision["implementation"] == "OllamaVisionProvider"
        assert vision["execution_mode"] == "local"
        assert vision["model"] == "moondream"
        assert "base_url" not in vision
        assert "reachable" not in vision["availability"]
    finally:
        ProviderRegistry.unregister("image_understanding")
