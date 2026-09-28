from fastapi.testclient import TestClient

from app.main import app
from app.services.devices.device_gateway_service import DeviceGatewayService
from app.services.providers.provider_registry import ProviderRegistry


def test_device_messages_are_bounded_persisted_redacted_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    message = {
        "message_id": "esp32-1",
        "device_id": "weather-sensor-1",
        "device_type": "esp32",
        "message_type": "telemetry",
        "payload": {"temperature_c": 22.5, "api_key": "secret"},
    }

    first = client.post("/devices/messages", json=message)
    duplicate = client.post("/devices/messages", json=message)
    assert first.status_code == 202
    assert first.json()["message"]["payload"]["api_key"] == "[REDACTED]"
    assert duplicate.json()["duplicate"] is True
    assert len(DeviceGatewayService().list_messages()) == 1
    assert client.get("/devices/messages").json()["messages"][0]["device_id"] == "weather-sensor-1"

    oversized = client.post(
        "/devices/messages",
        json={**message, "message_id": "oversized", "payload": {"data": "x" * 65_000}},
    )
    assert oversized.status_code == 422
    assert len(DeviceGatewayService().list_messages()) == 1


def test_device_commands_report_unavailable_until_transport_confirms_delivery(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    request = {"device_type": "esp32", "action": "set_led", "payload": {"enabled": True}}

    unavailable = client.post("/devices/lamp-1/commands", json=request)
    assert unavailable.status_code == 501
    assert unavailable.json()["detail"]["code"] == "provider_unavailable"

    class Transport:
        def send_command(self, device_id, device_type, action, payload):
            assert (device_id, device_type, action, payload) == ("lamp-1", "esp32", "set_led", {"enabled": True})
            return {"success": True, "command_id": "cmd-123"}

    ProviderRegistry.register("device_transport", Transport())
    try:
        sent = client.post("/devices/lamp-1/commands", json=request)
    finally:
        ProviderRegistry.clear()
    assert sent.status_code == 200
    assert sent.json() == {"success": True, "status": "sent", "command_id": "cmd-123", "device_id": "lamp-1", "device_type": "esp32"}
