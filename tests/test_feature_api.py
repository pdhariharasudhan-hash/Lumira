from fastapi import HTTPException

from app.routes import features


class FakeActivationService:
    def list_features(self):
        return {"success": True, "count": 28, "features": {}}

    def status(self, feature_id):
        if feature_id == "missing":
            return {"success": False, "error": "feature_not_found"}
        return {
            "success": True,
            "feature": feature_id,
            "metadata": {"feature_id": feature_id},
            "can_enable": feature_id != "blocked",
            "blockers": ["dependency unavailable"] if feature_id == "blocked" else [],
        }

    def activate(self, feature_id):
        if feature_id == "missing":
            return {"success": False, "error": "feature_not_found"}
        if feature_id == "blocked":
            return {"success": False, "feature": feature_id, "blockers": ["dependency unavailable"]}
        return {"success": True, "feature": feature_id, "status": "ENABLED"}

    def deactivate(self, feature_id):
        if feature_id == "missing":
            return {"success": False, "error": "feature_not_found"}
        if feature_id == "protected":
            return {"success": False, "feature": feature_id, "blockers": ["protected core feature"]}
        return {"success": True, "feature": feature_id, "status": "DISABLED"}


def test_feature_catalog_endpoint_exposes_complete_catalog(monkeypatch):
    monkeypatch.setattr(features, "FeatureActivationService", FakeActivationService)
    result = features.list_features()
    assert result["success"] is True
    assert result["count"] == 28


def test_feature_status_rejects_unknown_feature(monkeypatch):
    monkeypatch.setattr(features, "FeatureActivationService", FakeActivationService)
    try:
        features.get_feature("missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("unknown feature should return 404")


def test_feature_activation_reports_dependency_blockers(monkeypatch):
    monkeypatch.setattr(features, "FeatureActivationService", FakeActivationService)
    try:
        features.activate_feature("blocked")
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail["blockers"] == ["dependency unavailable"]
    else:
        raise AssertionError("blocked activation should return 409")


def test_feature_activation_and_deactivation_success(monkeypatch):
    monkeypatch.setattr(features, "FeatureActivationService", FakeActivationService)
    assert features.activate_feature("projects")["status"] == "ENABLED"
    assert features.deactivate_feature("projects")["status"] == "DISABLED"
