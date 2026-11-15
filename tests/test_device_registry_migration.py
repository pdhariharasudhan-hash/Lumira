import json

from app.services.devices.device_registry_service import DeviceRegistryService


def test_legacy_device_registry_adds_schema_marker_on_first_write(tmp_path):
    path = tmp_path / "devices.json"
    original = {"devices": [], "legacy_note": "preserve this field"}
    path.write_text(json.dumps(original), encoding="utf-8")
    service = DeviceRegistryService(path)

    assert service.list_devices() == []
    assert json.loads(path.read_text(encoding="utf-8")) == original

    service.register_device("board-1", "esp32")

    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == 1
    assert migrated["legacy_note"] == "preserve this field"
    assert [device["device_id"] for device in migrated["devices"]] == ["board-1"]