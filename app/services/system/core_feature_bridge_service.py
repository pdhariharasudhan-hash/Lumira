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
                status = self.features.status(feature_id)
                if status.get("success") is True and status.get("can_enable") is not True:
                    bucket["blocked"].append({
                        "feature": feature_id,
                        "blockers": status.get("blockers", []),
                    })

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

    def bridge_health(self):
        overview = self.overview()
        features = overview.get("features", {})
        categories = features.get("categories", {})
        blocked = sum(len(value.get("blocked", [])) for value in categories.values() if isinstance(value, dict))
        return {
            "success": True,
            "feature_total": features.get("total", 0),
            "enabled_count": len(features.get("enabled", [])),
            "failed_count": len(features.get("failed", [])),
            "blocked_count": blocked,
            "core_available": overview.get("core") is not None,
        }

    def plan(self, feature_id):
        return self.features.dependency_plan(feature_id)

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
