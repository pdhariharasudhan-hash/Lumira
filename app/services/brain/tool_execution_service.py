"""Permission-checked, audited async execution for registered Brain tools."""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from threading import Lock, RLock
from time import monotonic
from typing import Any, Awaitable, Callable, Mapping

from app.services.brain.tool_execution_policy_service import (
    ToolApprovalService,
    ToolExecutionBudget,
    ToolExecutionPolicyService,
)
from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
from app.services.security.security_audit_log_service import SecurityAuditLogService


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class ToolExecutionService:
    """Execute only explicitly registered, schema-valid and authorized tools.

    Every invocation must first be durably recorded in the hash-chained
    security log. If the pre-execution audit write fails, no handler is called.
    """

    _AUTONOMY_CAPABILITY_MAP = {
        "agent.dispatch": "agent.dispatch",
        "workflow.run": "workflow.run",
        "code.execute": "code.execute",
        "process.execute": "code.execute",
        "device.command": "device.command",
    }
    # One process-wide execution slot keeps tool concurrency bounded on the
    # low-memory local runtime, including across separate service instances.
    _execution_lock = Lock()

    def __init__(
        self,
        policy: ToolExecutionPolicyService | None = None,
        approvals: ToolApprovalService | None = None,
        audit_log: SecurityAuditLogService | None = None,
        autonomy_permissions: AutonomyPermissionService | None = None,
    ) -> None:
        self.policy = policy or ToolExecutionPolicyService()
        self.approvals = approvals or ToolApprovalService()
        self.audit_log = audit_log or SecurityAuditLogService()
        self.autonomy_permissions = autonomy_permissions or AutonomyPermissionService()
        self._tools: dict[str, tuple[dict[str, Any], ToolHandler]] = {}
        self._lock = RLock()

    def register(self, manifest: Mapping[str, Any], handler: ToolHandler) -> None:
        if not isinstance(manifest, Mapping):
            raise TypeError("tool manifest must be a mapping")
        normalized = json.loads(
            json.dumps(dict(manifest), ensure_ascii=False, allow_nan=False)
        )
        decision = self.policy.validate_manifest(normalized)
        if not decision.allowed:
            raise ValueError(f"invalid tool manifest: {decision.code}")
        if not callable(handler) or not (
            inspect.iscoroutinefunction(handler)
            or inspect.iscoroutinefunction(getattr(handler, "__call__", None))
        ):
            raise TypeError("tool handlers must be async callables")
        name = normalized["name"].strip()
        with self._lock:
            if name in self._tools:
                raise ValueError(f"tool already registered: {name}")
            self._tools[name] = (normalized, handler)

    def unregister(self, name: str) -> bool:
        if not isinstance(name, str) or not name.strip():
            return False
        with self._lock:
            return self._tools.pop(name.strip(), None) is not None

    def list_tools(self) -> list[str]:
        with self._lock:
            return sorted(self._tools)

    def grant_approval(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        user_confirmed: bool,
    ) -> dict[str, Any]:
        if not isinstance(tool_name, str) or not tool_name.strip():
            return {"success": False, "code": "invalid_tool_name"}
        with self._lock:
            if tool_name not in self._tools:
                return {"success": False, "code": "tool_not_found"}
        return self.approvals.grant(
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            user_confirmed=user_confirmed,
        )

    @staticmethod
    def _fingerprint(arguments: Any) -> str:
        try:
            payload = json.dumps(
                arguments,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return ""
        return hashlib.sha256(payload).hexdigest()

    def _audit(self, *, tool_name: str, session_id: str, outcome: str, arguments: Any, code: str) -> bool:
        try:
            self.audit_log.append(
                event_type="tool_execution",
                action="tool.invoke",
                outcome=outcome,
                actor="session:" + hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16],
                details={
                    "tool_name": tool_name[:128],
                    "arguments_sha256": self._fingerprint(arguments),
                    "result_code": code[:80],
                },
            )
            return True
        except Exception:
            return False

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        session_id: str,
        approval_id: str | None = None,
        budget: ToolExecutionBudget | None = None,
        autonomous: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(tool_name, str) or not tool_name.strip():
            return {"success": False, "code": "invalid_tool_name"}
        tool_name = tool_name.strip()
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 256:
            return {"success": False, "code": "invalid_session"}
        if not isinstance(autonomous, bool):
            return {"success": False, "code": "invalid_autonomy_mode"}

        with self._lock:
            registered = self._tools.get(tool_name)
        if registered is None:
            return {"success": False, "code": "tool_not_found"}
        manifest, handler = registered
        capability = manifest["capability"].strip()

        if autonomous:
            operation = self._AUTONOMY_CAPABILITY_MAP.get(capability)
            if operation is None:
                return {
                    "success": False,
                    "code": "autonomous_capability_not_supported",
                    "message": "This tool capability has no explicit autonomous permission mapping.",
                }
            try:
                authorization = self.autonomy_permissions.authorize(
                    operation,
                    autonomous=True,
                )
            except Exception:
                return {
                    "success": False,
                    "code": "autonomous_permission_state_unavailable",
                }
            if authorization.get("allowed") is not True:
                return {
                    "success": False,
                    "code": authorization.get("code", "autonomous_permission_required"),
                    "message": authorization.get("message", "Autonomous execution is not authorized."),
                }

        active_budget = budget or ToolExecutionBudget()
        try:
            payload_size = ToolExecutionPolicyService._json_size(arguments)
            if payload_size < 0:
                return {"success": False, "code": "invalid_arguments"}
            active_budget.begin_call(payload_size)
        except (RuntimeError, ValueError) as exc:
            return {
                "success": False,
                "code": "execution_budget_exceeded",
                "reason": str(exc),
            }

        decision = self.policy.authorize(
            manifest,
            arguments,
            approval_id=approval_id,
            session_id=session_id,
            approval_service=self.approvals,
        )
        if not decision.allowed:
            self._audit(
                tool_name=tool_name,
                session_id=session_id,
                outcome="denied",
                arguments=arguments,
                code=decision.code,
            )
            return {
                "success": False,
                "code": decision.code,
                "message": decision.message,
                "requires_approval": decision.requires_approval,
            }

        if not self._execution_lock.acquire(blocking=False):
            return {
                "success": False,
                "state": "deferred",
                "code": "tool_capacity_busy",
                "message": "Another tool invocation is active. The local runtime allows one tool execution at a time; retry after it finishes.",
            }

        try:
            if not self._audit(
                tool_name=tool_name,
                session_id=session_id,
                outcome="started",
                arguments=decision.normalized_arguments,
                code="started",
            ):
                return {
                    "success": False,
                    "code": "security_audit_unavailable",
                    "message": "Tool execution was blocked because its security audit event could not be persisted.",
                }

            remaining = active_budget.deadline - monotonic()
            if remaining <= 0:
                result = {"success": False, "code": "execution_budget_exceeded"}
            else:
                try:
                    value = await asyncio.wait_for(
                        handler(dict(decision.normalized_arguments or {})),
                        timeout=remaining,
                    )
                    bounded = self.policy.bound_result(value)
                    if bounded["success"] is not True:
                        result = bounded
                    else:
                        try:
                            active_budget.record_result(bounded["size_bytes"])
                            result = bounded
                        except (RuntimeError, ValueError):
                            result = {
                                "success": False,
                                "code": "execution_result_budget_exceeded",
                            }
                except asyncio.TimeoutError:
                    result = {"success": False, "code": "tool_execution_timeout"}
                except asyncio.CancelledError:
                    self._audit(
                        tool_name=tool_name,
                        session_id=session_id,
                        outcome="cancelled",
                        arguments=decision.normalized_arguments,
                        code="tool_execution_cancelled",
                    )
                    raise
                except Exception as exc:
                    result = {
                        "success": False,
                        "code": "tool_execution_failed",
                        "error_type": type(exc).__name__,
                    }

            outcome = "completed" if result.get("success") is True else "failed"
            if not self._audit(
                tool_name=tool_name,
                session_id=session_id,
                outcome=outcome,
                arguments=decision.normalized_arguments,
                code=str(result.get("code", "unknown")),
            ):
                return {
                    "success": False,
                    "code": "execution_outcome_audit_failed",
                    "message": "The handler returned, but Lumira could not persist the final security audit event.",
                    "side_effect_may_have_occurred": True,
                }
            return result
        finally:
            self._execution_lock.release()
