from app.services.features.feature_registry_service import FeatureRegistryService


class FeatureActivationService:
    """Controls safe, dependency-aware feature activation."""

    def __init__(self, registry: FeatureRegistryService | None = None):
        self.registry = registry or FeatureRegistryService()

    @staticmethod
    def _name(feature_name: str) -> str:
        if not isinstance(feature_name, str):
            return ""
        return feature_name.strip().lower()

    def activate(self, feature_name: str):
        name = self._name(feature_name)
        feature = self.registry.get_feature(name)
        if feature is None:
            return {"success": False, "action": "activate", "feature": name, "error": "feature_not_found"}
        name = feature.get("feature_id", name)
        allowed, blockers = self.registry.enable(name)
        feature = self.registry.get_feature(name)
        return {
            "success": allowed,
            "action": "activate",
            "feature": name,
            "status": feature.get("status") if feature else None,
            "metadata": feature,
            "blockers": blockers,
        }

    def deactivate(self, feature_name: str):
        name = self._name(feature_name)
        feature = self.registry.get_feature(name)
        if feature is None:
            return {"success": False, "action": "deactivate", "feature": name, "error": "feature_not_found"}
        name = feature.get("feature_id", name)
        allowed, blockers = self.registry.disable(name)
        feature = self.registry.get_feature(name)
        return {
            "success": allowed,
            "action": "deactivate",
            "feature": name,
            "status": feature.get("status") if feature else None,
            "metadata": feature,
            "blockers": blockers,
        }

    def status(self, feature_name: str):
        name = self._name(feature_name)
        feature = self.registry.get_feature(name)
        if feature is None:
            return {"success": False, "feature": name, "error": "feature_not_found"}
        name = feature.get("feature_id", name)
        can_enable, blockers = self.registry.can_enable(name)
        return {
            "success": True,
            "feature": name,
            "metadata": feature,
            "can_enable": can_enable,
            "blockers": blockers,
        }

    def list_features(self):
        features = self.registry.get_all()
        activation_blocked = {}
        for name, item in features.items():
            if item.get("enabled") or item.get("status") not in {"AVAILABLE", "EXPERIMENTAL", "DISABLED", "DEGRADED"}:
                continue
            can_enable, blockers = self.registry.can_enable(name)
            if not can_enable:
                activation_blocked[name] = blockers
        return {
            "success": True,
            "count": len(features),
            "enabled": [name for name, item in features.items() if item.get("enabled")],
            "available": [name for name, item in features.items() if item.get("status") == "AVAILABLE"],
            "activation_blocked": activation_blocked,
            "failed": [name for name, item in features.items() if item.get("status") == "FAILED"],
            "features": features,
        }
