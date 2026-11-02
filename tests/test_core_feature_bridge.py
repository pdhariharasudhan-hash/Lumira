from app.services.system.core_feature_bridge_service import CoreFeatureBridgeService


class Features:
    def list_features(self):
        return {
            "count": 2,
            "enabled": ["memory"],
            "available": ["goals"],
            "failed": [],
            "features": {
                "memory": {"category": "core", "enabled": True},
                "goals": {"category": "core_intelligence", "enabled": False},
            },
        }

    def status(self, feature_id):
        if feature_id != "goals":
            return {"success": False}
        return {
            "success": True,
            "feature": "goals",
            "metadata": {
                "enabled": False,
                "dependencies": ["memory"],
                "capabilities": ["goals.create"],
                "health": "healthy",
            },
            "can_enable": True,
            "blockers": [],
        }


class Status:
    def overview(self):
        return {"system": "ok"}


def test_core_feature_bridge_groups_features_and_readiness():
    service = CoreFeatureBridgeService(Features(), Status())
    overview = service.overview()
    assert overview["features"]["categories"]["core"]["enabled"] == ["memory"]
    readiness = service.readiness("goals")
    assert readiness["can_enable"] is True
    assert readiness["dependencies"] == ["memory"]
