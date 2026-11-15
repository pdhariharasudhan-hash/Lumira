import json

import pytest

from app.services.devices.device_profile_service import DeviceProfileService
from app.services.persistence.atomic_json_store import PersistenceIntegrityError


def test_future_device_profile_schema_is_rejected_without_rewrite(tmp_path):
    path = tmp_path / "device_profiles.json"
    original = {"schema_version": 99, "profiles": {"existing": {"profile_id": "existing"}}}
    path.write_text(json.dumps(original), encoding="utf-8")
    service = DeviceProfileService(path)

    with pytest.raises(PersistenceIntegrityError, match="schema"):
        service.list()
    with pytest.raises(PersistenceIntegrityError, match="schema"):
        service.register("new", "esp32")

    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_legacy_device_profile_store_migrates_additively_on_write(tmp_path):
    path = tmp_path / "device_profiles.json"
    original_profile = {
        "profile_id": "existing",
        "device_type": "esp32",
        "metadata": {"board": "ESP32"},
        "connection": "unverified",
    }
    path.write_text(
        json.dumps({"profiles": {"existing": original_profile}, "legacy_note": "preserve"}),
        encoding="utf-8",
    )
    service = DeviceProfileService(path)

    assert service.list() == [original_profile]
    service.register("new", "arduino")

    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == 1
    assert migrated["legacy_note"] == "preserve"
    assert migrated["profiles"]["existing"] == original_profile
    assert "new" in migrated["profiles"]
