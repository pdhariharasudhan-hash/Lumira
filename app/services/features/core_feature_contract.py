from typing import Any

from app.services.features.feature_registry_service import FeatureRegistryService


class CoreFeatureContract:
    """Validates the explicit intelligence state required by Lumira Core."""

    REQUIRED_STATE_FIELDS = (
        "current_stage",
        "last_completed_stage",
        "status",
        "goal",
        "objective",
        "intent",
        "context",
        "constraints",
        "decision",
        "plan",
        "selected_capability",
        "execution_result",
        "verification_result",
        "reflection",
        "learning",
        "memory_reference",
    )
    STRING_STATE_FIELDS = (
        "current_stage",
        "last_completed_stage",
        "intent",
        "selected_capability",
    )

    ALLOWED_STATUSES = {
        "running",
        "stopped",
        "completed",
        "blocked",
        "failed",
        "waiting",
        "recovering",
    }

    def __init__(self, registry: FeatureRegistryService | None = None):
        self.registry = registry or FeatureRegistryService()

    def validate_state(self, state: Any) -> dict[str, Any]:
        """Reject malformed state deterministically instead of raising TypeError."""
        if not isinstance(state, dict):
            return {
                "valid": False,
                "missing": list(self.REQUIRED_STATE_FIELDS),
                "invalid_fields": list(self.STRING_STATE_FIELDS),
                "invalid_status": False,
                "invalid_state_type": True,
                "status": None,
            }

        missing = [field for field in self.REQUIRED_STATE_FIELDS if field not in state]
        invalid_fields = [
            field for field in self.STRING_STATE_FIELDS
            if not isinstance(state.get(field), str)
        ]
        status = state.get("status")
        invalid_status = not isinstance(status, str) or status not in self.ALLOWED_STATUSES
        return {
            "valid": not missing and not invalid_status and not invalid_fields,
            "missing": missing,
            "invalid_fields": invalid_fields,
            "invalid_status": invalid_status,
            "invalid_state_type": False,
            "status": status if isinstance(status, (str, int, float, bool)) or status is None else "invalid",
        }

    def feature_ready(self, feature_name: str) -> dict[str, Any]:
        if not isinstance(feature_name, str) or not feature_name.strip():
            return {
                "ready": False,
                "feature": None,
                "reason": "invalid_feature_name",
            }
        feature = self.registry.get_feature(feature_name)
        if feature is None:
            return {
                "ready": False,
                "feature": feature_name,
                "reason": "feature_not_found",
            }
        enabled = bool(feature.get("enabled"))
        healthy = feature.get("health") in {"healthy", "degraded"}
        dependencies_ready, blockers = self.registry.can_enable(feature_name)
        return {
            "ready": enabled and healthy and dependencies_ready,
            "feature": feature_name,
            "enabled": enabled,
            "health": feature.get("health"),
            "status": feature.get("status"),
            "blockers": blockers,
        }
