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

    def activate_with_dependencies(self, feature_name: str):
        """Activate a feature and its dependency chain as one deterministic bridge."""
        name = self._name(feature_name)
        root = self.registry.get_feature(name)
        if root is None:
            return {"success": False, "feature": name, "error": "feature_not_found"}

        ordered = []
        visiting = set()
        visited = set()

        def visit(feature_id):
            if feature_id in visiting:
                raise ValueError("feature dependency cycle detected")
            if feature_id in visited:
                return
            item = self.registry.get_feature(feature_id)
            if item is None:
                raise ValueError(f"unknown feature dependency: {feature_id}")
            visiting.add(feature_id)
            for dependency in item.get("dependencies", []):
                visit(dependency)
            visiting.remove(feature_id)
            visited.add(feature_id)
            ordered.append(feature_id)

        try:
            visit(root.get("feature_id", name))
        except ValueError as exc:
            return {"success": False, "feature": name, "error": "dependency_resolution_failed", "blockers": [str(exc)]}

        activated = []
        for feature_id in ordered:
            item = self.registry.get_feature(feature_id)
            if item and item.get("enabled") is True:
                continue
            allowed, blockers = self.registry.enable(feature_id)
            if not allowed:
                return {
                    "success": False,
                    "feature": name,
                    "error": "activation_blocked",
                    "activated": activated,
                    "blocked_feature": feature_id,
                    "blockers": blockers,
                }
            activated.append(feature_id)

        return {
            "success": True,
            "action": "activate_with_dependencies",
            "feature": root.get("feature_id", name),
            "activation_order": ordered,
            "activated": activated,
            "status": "ENABLED",
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
