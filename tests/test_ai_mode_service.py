import json

from app.services.modes.ai_mode_service import AIModeService


def test_new_install_defaults_to_hybrid_without_cloud_consent(tmp_path):
    service = AIModeService(tmp_path / "ai_mode.json")
    assert service.get() == {
        "mode": "hybrid",
        "cloud_enabled": False,
        "local_providers_allowed": True,
        "network_allowed": False,
        "external_providers_allowed": False,
    }


def test_existing_offline_preference_is_preserved(tmp_path):
    path = tmp_path / "ai_mode.json"
    path.write_text(json.dumps({"schema_version": 1, "mode": "offline"}), encoding="utf-8")
    service = AIModeService(path)
    assert service.get()["mode"] == "offline"
    assert service.get()["cloud_enabled"] is False


def test_cloud_consent_is_separate_and_offline_always_blocks_external_providers(tmp_path):
    service = AIModeService(tmp_path / "ai_mode.json")
    service.set_cloud_enabled(True)
    assert service.get()["external_providers_allowed"] is True

    service.set("offline")
    policy = service.get()
    assert policy["cloud_enabled"] is True
    assert policy["network_allowed"] is False
    assert policy["external_providers_allowed"] is False

    service.set("hybrid")
    assert service.get()["external_providers_allowed"] is True


def test_cloud_consent_requires_a_real_boolean(tmp_path):
    service = AIModeService(tmp_path / "ai_mode.json")
    try:
        service.set_cloud_enabled("true")
    except ValueError as exc:
        assert "boolean" in str(exc)
    else:
        raise AssertionError("non-boolean cloud consent must be rejected")


def test_corrupt_mode_fails_closed_instead_of_silently_selecting_hybrid(tmp_path):
    path = tmp_path / "ai_mode.json"
    path.write_text(json.dumps({"schema_version": 1, "mode": "unknown", "cloud_enabled": True}), encoding="utf-8")
    service = AIModeService(path)
    try:
        service.get()
    except ValueError as error:
        assert "invalid mode" in str(error)
    else:
        raise AssertionError("invalid persisted mode must fail closed")


def test_cloud_consent_update_does_not_silently_rewrite_corrupt_mode(tmp_path):
    path = tmp_path / "ai_mode.json"
    original = {"schema_version": 1, "mode": "corrupt", "cloud_enabled": False}
    path.write_text(json.dumps(original), encoding="utf-8")
    service = AIModeService(path)
    try:
        service.set_cloud_enabled(True)
    except ValueError as error:
        assert "invalid mode" in str(error)
    else:
        raise AssertionError("cloud consent must not silently rewrite a corrupt mode")
    assert json.loads(path.read_text(encoding="utf-8")) == original
