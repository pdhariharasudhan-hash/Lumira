from __future__ import annotations

from typing import Any

from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
from app.services.capabilities.capability_router_service import CapabilityRouterService
from app.services.security.security_audit_log_service import SecurityAuditLogService
from app.services.security.unsafe_operation_detection_service import UnsafeOperationDetectionService


class BrainExecutionCoordinator:
    """Execute an explicitly requested capability after Brain verification."""

    _CODE_CAPABILITIES = {
        "code_generation",
        "debugging",
        "project_generation",
        "execute",
    }

    def __init__(self, router: CapabilityRouterService | None = None) -> None:
        self.router = router or CapabilityRouterService()

    def execute(
        self,
        *,
        capability: str,
        payload: dict[str, Any],
        ready_for_execution: bool,
        autonomous: bool = False,
        instruction: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(capability, str) or not capability.strip():
            return self._failure("invalid_capability", "A capability is required.")
        if not isinstance(payload, dict):
            return self._failure("invalid_payload", "Capability payload must be an object.")
        if ready_for_execution is not True:
            return self._failure(
                "verification_required",
                "The Brain plan was not verified for execution.",
            )

        normalized = capability.strip().lower()
        operation = self._permission_operation(normalized)
        if operation is not None and instruction is not None:
            preflight = UnsafeOperationDetectionService.analyze(instruction)
            allowed = preflight.get("success") is True and preflight.get("allowed") is True
            try:
                SecurityAuditLogService().append(
                    event_type="capability_preflight",
                    action=normalized,
                    outcome="allowed" if allowed else "blocked",
                    actor="main_brain",
                    details={
                        "finding_rules": [
                            item.get("rule")
                            for item in preflight.get("findings", [])
                            if isinstance(item, dict)
                        ],
                        "finding_count": len(preflight.get("findings", [])),
                    },
                )
            except Exception:
                return {
                    "success": False,
                    "status": "blocked",
                    "code": "security_audit_unavailable",
                    "message": "Security audit is unavailable; execution was blocked.",
                }
            if not allowed:
                return {
                    "success": False,
                    "status": "blocked",
                    "code": "unsafe_operation_requires_approval",
                    "message": "The requested operation was blocked by the security preflight.",
                    "security_preflight": preflight,
                }
        if operation is not None:
            authorization = AutonomyPermissionService().authorize(
                operation,
                autonomous=autonomous,
            )
            if authorization.get("allowed") is not True:
                return {
                    "success": False,
                    "status": "blocked",
                    "code": authorization.get("code", "permission_required"),
                    "message": authorization.get("message", "Permission required."),
                }

        try:
            result = self.router.execute(normalized, payload)
        except Exception as exc:
            return {
                "success": False,
                "status": "failed",
                "code": "capability_execution_failed",
                "error_type": type(exc).__name__,
            }
        if not isinstance(result, dict):
            return self._failure(
                "invalid_capability_result",
                "Capability execution returned an invalid result.",
            )
        if result.get("success") is False or str(result.get("status", "")).lower() in {
            "failed", "reject", "rejected", "blocked", "error",
        }:
            return {
                **result,
                "success": False,
                "status": result.get("status", "failed"),
            }
        return {**result, "success": True}

    @classmethod
    def _permission_operation(cls, capability: str) -> str | None:
        if capability in cls._CODE_CAPABILITIES:
            return "code.execute"
        if capability in {"workflow", "workflow_run"}:
            return "workflow.run"
        return None

    @staticmethod
    def _failure(code: str, message: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "code": code, "message": message}
