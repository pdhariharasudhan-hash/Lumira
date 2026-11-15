from __future__ import annotations

from typing import Any

from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
from app.services.capabilities.capability_router_service import CapabilityRouterService
from app.services.conversation.conversation_provider_router import (
    ConversationProviderRouter,
    ConversationProviderUnavailable,
)
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
    _WORKFLOW_CAPABILITIES = {
        "workflow",
        "workflow_run",
        "workflow_automation",
        "business_operations",
    }

    def __init__(
        self,
        router: CapabilityRouterService | None = None,
        conversation_router: ConversationProviderRouter | None = None,
    ) -> None:
        self.router = router or CapabilityRouterService()
        self.conversation_router = conversation_router or ConversationProviderRouter()

    def execute(
        self,
        *,
        capability: str,
        payload: dict[str, Any],
        ready_for_execution: bool,
        autonomous: bool = False,
        instruction: str | None = None,
        mode_state: Any = None,
    ) -> dict[str, Any]:
        if not isinstance(capability, str) or not capability.strip():
            return self._failure("invalid_capability", "A capability is required.")
        if not isinstance(payload, dict):
            return self._failure("invalid_payload", "Capability payload must be an object.")
        normalized = capability.strip().lower()
        if ready_for_execution is not True and normalized != "conversation":
            return self._failure(
                "verification_required",
                "The Brain plan was not verified for execution.",
            )

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
            if normalized == "conversation":
                result = self._execute_conversation(payload)
            elif mode_state is None:
                result = self.router.execute(normalized, payload)
            else:
                result = self.router.execute(
                    normalized,
                    payload,
                    mode_state=mode_state,
                )
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

    def _execute_conversation(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = payload.get("message")
        history = payload.get("history", [])
        context = payload.get("context", "")
        if not isinstance(message, str) or not message.strip() or len(message) > 10_000:
            return self._failure("invalid_conversation_message", "A conversation message is required.")
        if not isinstance(history, list):
            return self._failure("invalid_conversation_history", "Conversation history must be a list.")
        if not isinstance(context, str) or len(context) > 3_000:
            return self._failure("invalid_conversation_context", "Conversation context is invalid.")
        try:
            response = self.conversation_router.chat(
                message,
                history=history[-20:],
                context=context or None,
            )
        except ConversationProviderUnavailable as error:
            return {
                "success": False,
                "status": "unavailable",
                "code": error.code,
                "message": error.user_message,
            }
        except Exception:
            return {
                "success": False,
                "status": "failed",
                "code": "conversation_provider_error",
                "message": "The configured chat provider failed. Check Lumira's provider status and try again.",
            }
        if not isinstance(response, str) or not response.strip():
            return {
                "success": False,
                "status": "failed",
                "code": "provider_invalid_response",
                "message": "The configured chat provider returned no usable text response.",
            }
        return {
            "success": True,
            "status": "accept",
            "capability": "conversation",
            "message": response.strip(),
        }

    @classmethod
    def _permission_operation(cls, capability: str) -> str | None:
        if capability in cls._CODE_CAPABILITIES:
            return "code.execute"
        if capability in cls._WORKFLOW_CAPABILITIES:
            return "workflow.run"
        return None

    @staticmethod
    def _failure(code: str, message: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "code": code, "message": message}
