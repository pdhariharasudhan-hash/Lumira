import tempfile
from pathlib import Path

from app.services.features.feature_registry_service import FeatureRegistryService
from app.services.features.feature_activation_service import FeatureActivationService


def test_registry_contains_master_feature_groups():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        features = registry.get_all()
        required = {
            "intent", "goals", "planner", "agents", "learning", "sessions",
            "projects", "code", "workflows", "autonomous_development",
            "recovery", "artifact_manager", "unified_search", "voice_idea_capture",
            "audio_playback", "image_understanding", "image_generation", "web_access", "research",
            "device_management", "mode_management", "terminal", "project_preview",
            "notepad", "capability_system", "security", "observability",
        }
        assert required.issubset(features)
        for feature in features.values():
            assert feature["feature_id"]
            assert feature["version"]
            assert feature["status"] in {
                "AVAILABLE", "ENABLED", "DISABLED", "DEGRADED", "FAILED", "EXPERIMENTAL"
            }
            assert isinstance(feature["dependencies"], list)
            assert isinstance(feature["capabilities"], list)
            assert isinstance(feature["permissions"], list)


def test_activation_enforces_dependencies_and_dependents():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        activation = FeatureActivationService()
        activation.registry = registry

        result = activation.activate("code")
        assert result["success"] is False
        assert any("projects" in blocker for blocker in result["blockers"])

        assert activation.activate("projects")["success"] is True
        assert activation.activate("code")["success"] is True

        blocked = activation.deactivate("projects")
        assert blocked["success"] is False
        assert "enabled dependents: code" in blocked["blockers"]


def test_core_features_cannot_be_disabled():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        ok, blockers = registry.disable("memory")
        assert ok is False
        assert blockers == ["memory is a protected core feature"]


def test_registry_persists_feature_state():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "features.json")
        first = FeatureRegistryService(path)
        ok, blockers = first.enable("artifact_manager")
        assert ok is True
        assert blockers == []

        second = FeatureRegistryService(path)
        assert second.is_enabled("artifact_manager") is True
        assert second.get_feature("artifact_manager")["status"] == "ENABLED"



def test_registry_repairs_malformed_catalog_entries_without_resetting_valid_state():
    import json

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "features.json"
        path.write_text(
            json.dumps({
                "memory": {
                    "feature_id": "memory",
                    "version": "1.0",
                    "category": "core",
                    "status": "ENABLED",
                    "dependencies": [],
                    "capabilities": ["memory.get"],
                    "configuration": {},
                    "permissions": [],
                    "health": "healthy",
                    "tests": True,
                    "enabled": True,
                },
                "intent": {
                    "feature_id": "intent",
                    "status": ["malformed"],
                    "dependencies": "memory",
                    "capabilities": [],
                    "configuration": [],
                    "permissions": [],
                    "health": ["invalid"],
                    "enabled": "yes",
                },
                "projects": {"status": "ENABLED"},
                "broken_extension": ["not", "an", "object"],
            }),
            encoding="utf-8",
        )

        registry = FeatureRegistryService(str(path))
        features = registry.get_all()

        assert features["memory"]["enabled"] is True
        assert features["projects"]["enabled"] is True
        assert isinstance(features["intent"]["dependencies"], list)
        assert isinstance(features["intent"]["configuration"], dict)
        assert features["intent"]["status"] in {
            "AVAILABLE", "ENABLED", "DISABLED", "DEGRADED", "FAILED", "EXPERIMENTAL"
        }
        assert isinstance(features["intent"]["health"], str)
        assert "broken_extension" not in features


def test_registry_refuses_to_reset_corrupt_or_non_object_persisted_state(tmp_path):
    import json
    import pytest
    from app.services.persistence.atomic_json_store import PersistenceIntegrityError

    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("{broken", encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError):
        FeatureRegistryService(str(corrupt_path))
    assert corrupt_path.read_text(encoding="utf-8") == "{broken"

    non_object_path = tmp_path / "non_object.json"
    non_object_path.write_text(json.dumps(["unexpected"]), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="must be an object"):
        FeatureRegistryService(str(non_object_path))
    assert json.loads(non_object_path.read_text(encoding="utf-8")) == ["unexpected"]


def test_registry_lifecycle_rejects_malformed_health_values():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        assert registry.update_health("intent", ["healthy"]) is False


def test_registry_rejects_invalid_names_and_duplicate_core_registration():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))

        assert registry.get_feature(["memory"]) is None
        assert registry.feature_exists(["memory"]) is False
        assert registry.enable(["memory"])[0] is False
        assert registry.disable("")[0] is False

        try:
            registry.register("memory", {"status": "AVAILABLE"})
        except ValueError as exc:
            assert "already exists" in str(exc)
        else:
            raise AssertionError("register must not overwrite a core feature")

        assert registry.get_feature("memory")["enabled"] is True


def test_registry_rejects_invalid_registration_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))

        try:
            registry.register("custom", {"status": ["ENABLED"]})
        except ValueError as exc:
            assert "status is invalid" in str(exc)
        else:
            raise AssertionError("invalid feature status was accepted")


def test_registry_never_registers_failed_health_as_enabled(tmp_path):
    import json

    path = tmp_path / "features.json"
    registry = FeatureRegistryService(str(path))
    item = registry.register("broken_extension", {
        "status": "ENABLED",
        "health": "failed",
    })

    assert item["status"] == "FAILED"
    assert item["enabled"] is False
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["broken_extension"]["status"] == "FAILED"
    assert persisted["broken_extension"]["enabled"] is False


def test_activation_service_handles_non_string_feature_names():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        activation = FeatureActivationService(registry)
        result = activation.activate(["memory"])
        assert result["success"] is False
        assert result["error"] == "feature_not_found"



def test_registry_repairs_mismatched_status_and_enabled_flags(tmp_path):
    import json

    path = tmp_path / "features.json"
    path.write_text(json.dumps({
        "intent": {"status": "ENABLED", "enabled": False},
        "projects": {"status": "AVAILABLE", "enabled": True},
        "web_access": {"status": "ENABLED", "enabled": True, "health": "failed"},
    }), encoding="utf-8")

    registry = FeatureRegistryService(str(path))
    features = registry.get_all()

    assert features["intent"]["status"] == "ENABLED"
    assert features["intent"]["enabled"] is True
    assert features["projects"]["status"] == "AVAILABLE"
    assert features["projects"]["enabled"] is False
    assert features["web_access"]["status"] == "FAILED"
    assert features["web_access"]["enabled"] is False

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["intent"]["enabled"] is True
    assert persisted["projects"]["enabled"] is False
    assert persisted["web_access"]["status"] == "FAILED"
    assert persisted["web_access"]["enabled"] is False



def test_registry_resolves_human_readable_and_hyphenated_feature_names(tmp_path):
    path = str(tmp_path / "features.json")
    registry = FeatureRegistryService(path)

    assert registry.get_feature("image generation")["feature_id"] == "image_generation"
    assert registry.get_feature("image-generation")["feature_id"] == "image_generation"
    assert registry.feature_exists("voice idea capture")
    assert registry.feature_exists("voice-idea-capture")
    assert registry.get_feature("voice capture")["feature_id"] == "voice_idea_capture"
    assert registry.get_feature("idea capture")["feature_id"] == "voice_idea_capture"
    assert registry.get_feature("  IMAGE   GENERATION  ")["feature_id"] == "image_generation"


def test_provider_backed_features_report_real_provider_blockers(tmp_path, monkeypatch):
    from app.services.providers.provider_registry import ProviderRegistry

    monkeypatch.setattr(ProviderRegistry, "get", classmethod(lambda cls, name: None))
    registry = FeatureRegistryService(str(tmp_path / "features.json"))

    for feature_id, provider_name in (
        ("voice_idea_capture", "transcription"),
        ("image_generation", "image_generation"),
        ("research", "research"),
    ):
        allowed, blockers = registry.can_enable(feature_id)
        assert allowed is False
        assert any(provider_name in blocker for blocker in blockers)

    allowed, blockers = registry.can_enable("image_understanding")
    assert allowed is False
    assert any("image-understanding provider is not configured" in blocker for blocker in blockers)


def test_image_understanding_can_be_enabled_when_provider_and_dependencies_are_ready(tmp_path, monkeypatch):
    from app.services.providers.provider_registry import ProviderRegistry

    monkeypatch.setattr(ProviderRegistry, "get", classmethod(lambda cls, name: object() if name == "image_understanding" else None))
    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    assert registry.enable("artifact_manager")[0] is True
    allowed, blockers = registry.can_enable("image_understanding")
    assert allowed is True
    assert blockers == []


def test_disabled_provider_feature_still_shows_activation_blockers(tmp_path, monkeypatch):
    from app.services.features.feature_activation_service import FeatureActivationService
    from app.services.providers.provider_registry import ProviderRegistry

    monkeypatch.setattr(ProviderRegistry, "get", classmethod(lambda cls, name: None))
    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    assert registry.disable("image_generation")[0] is True
    listing = FeatureActivationService(registry).list_features()
    blockers = listing["activation_blocked"]["image_generation"]
    assert any("image_generation" in blocker for blocker in blockers)


def test_activation_checks_transitive_dependency_readiness(tmp_path):
    import json

    path = tmp_path / "features.json"
    registry = FeatureRegistryService(str(path))
    assert registry.enable("projects")[0] is True
    assert registry.enable("code")[0] is True
    assert registry.enable("workflows")[0] is True

    # Simulate stale persisted state: direct dependents remain enabled even
    # though their shared transitive core dependency is no longer enabled.
    features = json.loads(path.read_text(encoding="utf-8"))
    features["memory"]["status"] = "DISABLED"
    features["memory"]["enabled"] = False
    path.write_text(json.dumps(features), encoding="utf-8")

    registry = FeatureRegistryService(str(path))
    allowed, blockers = registry.can_enable("autonomous_development")

    assert allowed is False
    assert any("projects -> memory" in blocker for blocker in blockers)


def test_activation_reports_persisted_dependency_cycles(tmp_path):
    import json

    path = tmp_path / "features.json"
    registry = FeatureRegistryService(str(path))
    features = json.loads(path.read_text(encoding="utf-8"))
    features["intent"].update(status="ENABLED", enabled=True, dependencies=["goals"])
    features["goals"].update(status="ENABLED", enabled=True, dependencies=["intent"])
    path.write_text(json.dumps(features), encoding="utf-8")

    registry = FeatureRegistryService(str(path))
    allowed, blockers = registry.can_enable("intent")

    assert allowed is False
    assert any("feature dependency cycle detected" in blocker for blocker in blockers)


def test_terminal_sandbox_gate_applies_to_transitive_dependencies(tmp_path):
    import json

    path = tmp_path / "features.json"
    registry = FeatureRegistryService(str(path))
    registry.register("terminal_dependent", {
        "status": "AVAILABLE",
        "dependencies": ["terminal"],
    })
    features = json.loads(path.read_text(encoding="utf-8"))
    # Simulate corrupted/stale persisted state; this must not bypass the gate.
    features["terminal"]["status"] = "ENABLED"
    features["terminal"]["enabled"] = True
    path.write_text(json.dumps(features), encoding="utf-8")

    registry = FeatureRegistryService(str(path))
    allowed, blockers = registry.can_enable("terminal_dependent")

    assert allowed is False
    assert any("verified OS-level sandbox is not implemented" in blocker for blocker in blockers)


def test_image_understanding_readiness_mentions_local_and_remote_provider_options(monkeypatch, tmp_path):
    from app.services.providers.provider_registry import ProviderRegistry

    monkeypatch.setattr(ProviderRegistry, "get", classmethod(lambda cls, name: None))
    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    allowed, blockers = registry.can_enable("image_understanding")

    assert allowed is False
    assert any("LUMIRA_VISION_API_KEY" in blocker for blocker in blockers)
    assert any("LUMIRA_OLLAMA_VISION_ENABLED" in blocker for blocker in blockers)
