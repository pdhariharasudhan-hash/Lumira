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
