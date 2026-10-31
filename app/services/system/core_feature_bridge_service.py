from app.services.features.feature_activation_service import FeatureActivationService
from app.services.system.personal_ai_status_service import PersonalAIStatusService


class CoreFeatureBridgeService:
    """Expose one core-facing view of Lumira's feature graph and readiness."""

    def __init__(self, features=None, status=None):
        self.features = features or FeatureActivationService()
        self.status_service = status or PersonalAIStatusService()

    def overview(self):
        catalog = self.features.list_features()
        features = catalog.get("features", {})
        categories = {}
        for feature_id, item in features.items():
            category = str(item.get("category") or "uncategorized")
            bucket = categories.setdefault(category, {"total": 0, "enabled": [], "blocked": []})
            bucket["total"] += 1
            if item.get("enabled") is True:
                bucket["enabled"].append(feature_id)
            else:
                ready, blockers = self.features.registry.can_enable(feature_id)
                if not ready:
                    bucket["blocked"].append({"feature": feature_id, "blockers": blockers})

        return {
            "success": True,
            "core": self.status_service.overview(),
            "features": {
                "total": catalog.get("count", len(features)),
                "enabled": catalog.get("enabled", []),
                "available": catalog.get("available", []),
                "failed": catalog.get("failed", []),
                "categories": categories,
            },
        }

    def readiness(self, feature_id):
        result = self.features.status(feature_id)
        if result.get("success") is not True:
            return result
        metadata = result.get("metadata", {})
        return {
            "success": True,
            "feature": result.get("feature"),
            "enabled": metadata.get("enabled") is True,
            "dependencies": metadata.get("dependencies", []),
            "capabilities": metadata.get("capabilities", []),
            "can_enable": result.get("can_enable") is True,
            "blockers": result.get("blockers", []),
            "health": metadata.get("health"),
        }
