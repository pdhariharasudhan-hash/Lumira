from app.services.system.core_feature_bridge_service import CoreFeatureBridgeService


class Features:
    def dependency_plan(self, feature_id):
        if feature_id == "missing":
            return {"success": False}
        return {"success": True, "feature": feature_id, "ready": True, "activation_order": [feature_id]}

    def list_features(self):
        return {"features": {}, "count": 0, "enabled": [], "available": [], "failed": []}

    def status(self, feature_id):
        return {"success": False}


class Status:
    def snapshot(self):
        return {"knowledge": {}, "features": {}, "recovery": {}}

    def overview(self):
        return self.snapshot()


def test_core_bridge_exposes_dependency_plan():
    service = CoreFeatureBridgeService(Features(), Status())
    result = service.plan("goals")
    assert result["success"] is True
    assert result["activation_order"] == ["goals"]
