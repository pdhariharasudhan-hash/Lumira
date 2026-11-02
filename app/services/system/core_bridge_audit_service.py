"""Repository-level bridge audit helpers."""

from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService


class CoreBridgeAuditService:
    REQUIRED_KEYS = {
        "status", "features", "resources", "artifacts", "voice",
        "memory", "recovery", "learning", "projects", "devices",
        "agents", "personal_context", "request_bridge",
    }

    def audit(self):
        overview = CoreRuntimeBridgeService().overview()
        overview["request_bridge"] = {"success": True, "data": {"scope": "all_api_requests"}}
        missing = sorted(key for key in self.REQUIRED_KEYS if key not in overview)
        unavailable = sorted(
            key for key in self.REQUIRED_KEYS
            if isinstance(overview.get(key), dict)
            and overview[key].get("success") is False
        )
        return {
            "success": not missing,
            "required": sorted(self.REQUIRED_KEYS),
            "missing": missing,
            "unavailable": unavailable,
            "bridge_complete": not missing,
        }
