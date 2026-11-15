"""Permission-checked runtime bridge for explicitly registered in-process plugins.

This service never imports plugin packages or executes manifest-supplied code.
A trusted application component must register an async handler in-process.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Awaitable, Callable, Mapping

from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
from app.services.brain.tool_execution_policy_service import (
    ToolApprovalService,
    ToolExecutionBudget,
    ToolExecutionPolicyService,
)
from app.services.brain.tool_execution_service import ToolExecutionService
from app.services.plugins.plugin_registry import PluginRegistry
from app.services.security.security_audit_log_service import SecurityAuditLogService


PluginHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class _RegisteredHandler:
    plugin_id: str
    capability: str
    tool_name: str
    required_permissions: tuple[str, ...]
    executor: ToolExecutionService


class PluginRuntimeService:
    """Bind approved plugin metadata to trusted, application-registered handlers."""

    MAX_REQUIRED_PERMISSIONS = 16

    def __init__(
        self,
        registry: PluginRegistry | None = None,
        audit_log: SecurityAuditLogService | None = None,
        autonomy_permissions: AutonomyPermissionService | None = None,
    ) -> None:
        self.registry = registry or PluginRegistry()
        self.audit_log = audit_log or SecurityAuditLogService()
        self.autonomy_permissions = autonomy_permissions or AutonomyPermissionService(
            audit_log=self.audit_log
        )
        self._handlers: dict[tuple[str, str], _RegisteredHandler] = {}
        self._lock = RLock()

    @staticmethod
    def _tool_name(plugin_id: str, capability: str) -> str:
        normalized = (
            "plugin_"
            + plugin_id.replace(".", "_").replace("-", "_")
            + "_"
            + capability.replace(".", "_").replace("-", "_")
        )
        if len(normalized) > ToolExecutionPolicyService.MAX_TOOL_NAME:
            raise ValueError("plugin capability identifier is too long for the tool registry")
        return normalized

    def _approved_record(
        self, plugin_id: str, required_permissions: tuple[str, ...]
    ) -> dict:
        record = self.registry.get(plugin_id)
        if not isinstance(record, dict):
            raise KeyError("plugin_not_found")
        if record.get("approval_state") != "approved":
            raise PermissionError("plugin_not_approved")
        manifest = record.get("manifest")
        grants = record.get("granted_permissions")
        if not isinstance(manifest, dict) or not isinstance(grants, list):
            raise ValueError("plugin_registry_record_invalid")
        declared = manifest.get("permissions")
        capabilities = manifest.get("capabilities")
        if not isinstance(declared, list) or not isinstance(capabilities, list):
            raise ValueError("plugin_manifest_invalid")
        if not set(required_permissions).issubset(set(declared)):
            raise PermissionError("plugin_permission_not_declared")
        if not set(required_permissions).issubset(set(grants)):
            raise PermissionError("plugin_permission_not_granted")
        return record

    def register_handler(
        self,
        plugin_id: str,
        capability: str,
        tool_manifest: Mapping[str, Any],
        handler: PluginHandler,
        *,
        required_permissions: tuple[str, ...] | list[str] = (),
    ) -> dict:
        if not isinstance(plugin_id, str) or not plugin_id.strip():
            raise ValueError("plugin_id is invalid")
        if not isinstance(capability, str) or not capability.strip() or len(capability) > 128:
            raise ValueError("capability is invalid")
        if not isinstance(required_permissions, (tuple, list)):
            raise ValueError("required_permissions must be a list")
        if len(required_permissions) > self.MAX_REQUIRED_PERMISSIONS:
            raise ValueError("too many required plugin permissions")
        if any(not isinstance(item, str) or not item.strip() for item in required_permissions):
            raise ValueError("required_permissions contains an invalid value")
        permissions = tuple(dict.fromkeys(item.strip() for item in required_permissions))
        record = self._approved_record(plugin_id.strip(), permissions)
        manifest = record["manifest"]
        if capability not in manifest["capabilities"]:
            raise PermissionError("plugin_capability_not_declared")
        if not isinstance(tool_manifest, Mapping):
            raise ValueError("tool_manifest must be a mapping")

        normalized = dict(tool_manifest)
        normalized["name"] = self._tool_name(plugin_id.strip(), capability)
        normalized["capability"] = capability
        executor = ToolExecutionService(
            policy=ToolExecutionPolicyService(permissions={capability: True}),
            approvals=ToolApprovalService(),
            audit_log=self.audit_log,
            autonomy_permissions=self.autonomy_permissions,
        )
        executor.register(normalized, handler)
        key = (plugin_id.strip(), capability)
        registered = _RegisteredHandler(
            plugin_id=key[0],
            capability=capability,
            tool_name=normalized["name"],
            required_permissions=permissions,
            executor=executor,
        )
        with self._lock:
            if key in self._handlers:
                raise ValueError("plugin capability handler is already registered")
            self._handlers[key] = registered
        return {
            "success": True,
            "plugin_id": key[0],
            "capability": capability,
            "handler_registered": True,
            "execution_enabled": True,
            "runtime": "trusted_in_process_handler",
        }

    def unregister_handler(self, plugin_id: str, capability: str) -> bool:
        if not isinstance(plugin_id, str) or not isinstance(capability, str):
            return False
        with self._lock:
            return self._handlers.pop((plugin_id.strip(), capability.strip()), None) is not None

    def list_handlers(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "plugin_id": item.plugin_id,
                    "capability": item.capability,
                    "required_permissions": list(item.required_permissions),
                    "runtime": "trusted_in_process_handler",
                }
                for _, item in sorted(self._handlers.items())
            ]

    def grant_approval(
        self,
        plugin_id: str,
        capability: str,
        arguments: dict[str, Any],
        *,
        session_id: str,
        user_confirmed: bool,
    ) -> dict:
        key = (plugin_id.strip(), capability.strip()) if isinstance(plugin_id, str) and isinstance(capability, str) else ("", "")
        with self._lock:
            registered = self._handlers.get(key)
        if registered is None:
            return {"success": False, "code": "plugin_handler_not_found"}
        try:
            record = self._approved_record(registered.plugin_id, registered.required_permissions)
            if capability not in record["manifest"].get("capabilities", []):
                return {"success": False, "code": "plugin_capability_not_declared"}
        except (KeyError, PermissionError, ValueError):
            return {"success": False, "code": "plugin_permission_unavailable"}
        except Exception:
            return {"success": False, "code": "plugin_registry_unavailable"}
        return registered.executor.grant_approval(
            session_id=session_id,
            tool_name=registered.tool_name,
            arguments=arguments,
            user_confirmed=user_confirmed,
        )

    async def execute(
        self,
        plugin_id: str,
        capability: str,
        arguments: dict[str, Any],
        *,
        session_id: str,
        approval_id: str | None = None,
        budget: ToolExecutionBudget | None = None,
        autonomous: bool = False,
    ) -> dict:
        if not isinstance(plugin_id, str) or not isinstance(capability, str):
            return {"success": False, "code": "invalid_plugin_reference"}
        key = (plugin_id.strip(), capability.strip())
        with self._lock:
            registered = self._handlers.get(key)
        if registered is None:
            return {"success": False, "code": "plugin_handler_not_found"}
        try:
            record = self._approved_record(
                registered.plugin_id,
                registered.required_permissions,
            )
        except KeyError:
            return {"success": False, "code": "plugin_not_found"}
        except PermissionError:
            return {"success": False, "code": "plugin_permission_unavailable"}
        except Exception:
            return {"success": False, "code": "plugin_registry_unavailable"}
        if capability not in record["manifest"].get("capabilities", []):
            return {"success": False, "code": "plugin_capability_not_declared"}
        return await registered.executor.execute(
            registered.tool_name,
            arguments,
            session_id=session_id,
            approval_id=approval_id,
            budget=budget,
            autonomous=autonomous,
        )
