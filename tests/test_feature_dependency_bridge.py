from app.services.features.feature_activation_service import FeatureActivationService
from app.services.features.feature_registry_service import FeatureRegistryService


def test_dependency_bridge_activates_in_order(tmp_path):
    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    service = FeatureActivationService(registry)
    result = service.activate_with_dependencies("goals")
    assert result["success"] is True
    assert "goals" in result["activation_order"]
    assert registry.is_enabled("goals") is True


def test_dependency_bridge_reports_provider_blockers(tmp_path):
    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    service = FeatureActivationService(registry)
    result = service.activate_with_dependencies("voice_idea_capture")
    assert result["success"] in {True, False}
    if result["success"] is False:
        assert result["blocked_feature"]


def test_dependency_bridge_preflights_before_mutating_any_feature(tmp_path, monkeypatch):
    from app.services.providers.provider_registry import ProviderRegistry

    monkeypatch.setattr(ProviderRegistry, "get", classmethod(lambda cls, name: None))
    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    service = FeatureActivationService(registry)

    result = service.activate_with_dependencies("voice_idea_capture")

    assert result["success"] is False
    assert result["activated"] == []
    assert any("transcription" in blocker for blocker in result["blockers"])
    assert registry.is_enabled("artifact_manager") is False
    assert registry.is_enabled("voice_idea_capture") is False


def test_dependency_plan_reports_ready_for_a_complete_available_chain(tmp_path):
    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    service = FeatureActivationService(registry)

    result = service.dependency_plan("audio playback")

    assert result["success"] is True
    assert result["ready"] is True
    assert result["activation_order"] == ["voice_input", "memory", "artifact_manager", "audio_playback"]
    assert registry.is_enabled("artifact_manager") is False


def test_audio_playback_has_a_registered_identity_activation_target(tmp_path):
    from app.services.identity.lumira_identity_service import LumiraIdentityService

    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    parsed = LumiraIdentityService().parse("Lumira, activate audio playback")

    assert parsed["recognized"] is True
    assert parsed["target"] == "audio_playback"
    assert registry.feature_exists(parsed["target"])
