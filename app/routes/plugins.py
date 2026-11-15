"""Owner-controlled plugin manifest and permission lifecycle API.

The registry stores metadata only. These endpoints never import, install, or
execute third-party plugin code.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.services.plugins.plugin_registry import (
    PluginManifestError,
    PluginRegistry,
    PluginRegistryError,
)
from app.services.security.security_audit_log_service import SecurityAuditLogService
from app.services.sessions.session_manager_service import SessionManagerService

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: dict[str, Any]


class PluginApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool
    granted_permissions: list[str] = Field(max_length=32)


class PluginRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool
    permission: str = Field(min_length=1, max_length=128)


class PluginDisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool


class PluginExecutionApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool
    session_id: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any] = Field(default_factory=dict)


class PluginExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any] = Field(default_factory=dict)
    approval_id: str | None = Field(default=None, max_length=128)
    autonomous: StrictBool = False


def _runtime(request: Request):
    runtime = getattr(request.app.state, "plugin_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="Plugin runtime is not initialized.")
    return runtime


def _registry() -> PluginRegistry:
    return PluginRegistry()


def _require_session(session_id: str) -> None:
    try:
        if SessionManagerService().get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="session not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Session authorization state is unavailable.") from exc


def _audit(action: str, outcome: str, plugin_id: str, details: dict | None = None) -> None:
    SecurityAuditLogService().append(
        event_type="plugin_lifecycle",
        action=action,
        outcome=outcome,
        actor="local_owner",
        details={"plugin_id": plugin_id, **(details or {})},
    )


def _safe_record(record: dict) -> dict:
    manifest = record.get("manifest", {})
    return {
        "manifest": manifest,
        "approval_state": record.get("approval_state"),
        "granted_permissions": list(record.get("granted_permissions", [])),
        "dynamic_code_execution_enabled": False,
        "runtime": "trusted_in_process_handlers_only",
    }


@router.get("")
def list_plugins():
    try:
        records = _registry().list_plugins()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Plugin registry is unavailable.") from exc
    return {
        "success": True,
        "plugins": {plugin_id: _safe_record(record) for plugin_id, record in records.items()},
        "count": len(records),
        "dynamic_code_execution_enabled": False,
        "trusted_handler_runtime": "explicit_application_registration_only",
    }


@router.get("/capabilities")
def list_approved_plugin_capabilities():
    try:
        capabilities = _registry().approved_capabilities()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Plugin capability registry is unavailable.") from exc
    return {
        "success": True,
        "capabilities": capabilities,
        "dynamic_code_execution_enabled": False,
        "trusted_handler_runtime": "explicit_application_registration_only",
    }


@router.get("/runtime/handlers")
def list_plugin_runtime_handlers(request: Request):
    return {"success": True, "handlers": _runtime(request).list_handlers()}


@router.post("/{plugin_id}/capabilities/{capability}/approval")
def approve_plugin_capability_execution(
    plugin_id: str,
    capability: str,
    request: PluginExecutionApprovalRequest,
    http_request: Request,
):
    _require_session(request.session_id)
    result = _runtime(http_request).grant_approval(
        plugin_id,
        capability,
        request.arguments,
        session_id=request.session_id,
        user_confirmed=request.confirm,
    )
    if result.get("success") is not True:
        status = 503 if result.get("code") == "plugin_registry_unavailable" else 403 if result.get("code") == "plugin_permission_unavailable" else 404 if result.get("code") == "plugin_handler_not_found" else 409
        raise HTTPException(status_code=status, detail=result)
    return result


@router.post("/{plugin_id}/capabilities/{capability}/execute")
async def execute_plugin_capability(
    plugin_id: str,
    capability: str,
    request: PluginExecutionRequest,
    http_request: Request,
):
    _require_session(request.session_id)
    result = await _runtime(http_request).execute(
        plugin_id,
        capability,
        request.arguments,
        session_id=request.session_id,
        approval_id=request.approval_id,
        autonomous=request.autonomous,
    )
    if result.get("success") is not True:
        code = result.get("code")
        status = 503 if code in {
            "security_audit_unavailable",
            "execution_outcome_audit_failed",
            "plugin_registry_unavailable",
        } else 403 if code in {
            "plugin_permission_unavailable",
            "permission_denied",
            "autonomous_permission_required",
            "autonomous_permission_state_unavailable",
        } else 404 if code in {
            "plugin_not_found",
            "plugin_handler_not_found",
        } else 504 if code == "tool_execution_timeout" else 409 if code in {
            "approval_required",
            "approval_missing_or_consumed",
            "approval_expired",
            "approval_context_mismatch",
            "tool_capacity_busy",
        } else 422
        raise HTTPException(status_code=status, detail=result)
    return result


@router.post("/register", status_code=201)
def register_plugin(request: PluginRegisterRequest):
    registry = _registry()
    try:
        from app.services.plugins.plugin_registry import PluginRegistry
        manifest = PluginRegistry.validate_manifest(request.manifest)
        _audit("plugin.register", "requested", manifest.plugin_id)
        record = registry.register(manifest)
    except PluginManifestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Plugin registration could not be completed safely.") from exc
    try:
        _audit("plugin.register", "completed", manifest.plugin_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "plugin_registration_audit_failed", "side_effect_may_have_occurred": True},
        ) from exc
    return {"success": True, "plugin": _safe_record(record)}


@router.post("/{plugin_id}/approve")
def approve_plugin(plugin_id: str, request: PluginApprovalRequest, http_request: Request):
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    registry = _registry()
    try:
        _audit("plugin.approve", "requested", plugin_id, {"permission_count": len(request.granted_permissions)})
        record = registry.approve(plugin_id, request.granted_permissions)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plugin not found.") from exc
    except (ValueError, PluginRegistryError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Plugin approval could not be completed safely.") from exc
    binding = None
    plugin_runtime = getattr(http_request.app.state, "plugin_runtime", None)
    if plugin_runtime is not None and record.get("approval_state") == "approved":
        from app.services.plugins.builtin_plugin_handlers import bind_approved_builtin_handlers
        # Only exact, application-owned capabilities are bindable. This does
        # not execute plugin code and does not widen the owner's grants.
        binding = bind_approved_builtin_handlers(plugin_runtime)
    try:
        _audit("plugin.approve", "completed", plugin_id, {
            "approval_state": record.get("approval_state"),
            "builtin_handlers_registered": binding.get("registered", 0) if isinstance(binding, dict) else 0,
        })
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "plugin_approval_audit_failed", "side_effect_may_have_occurred": True},
        ) from exc
    return {
        "success": True,
        "plugin": _safe_record(record),
        "runtime_binding": binding,
    }


@router.post("/{plugin_id}/revoke")
def revoke_plugin_permission(plugin_id: str, request: PluginRevokeRequest, http_request: Request):
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    registry = _registry()
    try:
        _audit("plugin.permission.revoke", "requested", plugin_id, {"permission": request.permission})
        record = registry.revoke(plugin_id, request.permission)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plugin not found.") from exc
    except (ValueError, PluginRegistryError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Plugin permission revocation could not be completed safely.") from exc
    # Revocation may also disable dependent plugins; reconcile the complete
    # in-process handler set so no withdrawn capability remains advertised.
    runtime = getattr(http_request.app, "state", None)
    if runtime is not None:
        plugin_runtime = getattr(runtime, "plugin_runtime", None)
        if plugin_runtime is not None:
            plugin_runtime.reconcile_handlers()
    try:
        _audit("plugin.permission.revoke", "completed", plugin_id, {"permission": request.permission})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "plugin_revocation_audit_failed", "side_effect_may_have_occurred": True},
        ) from exc
    return {"success": True, "plugin": _safe_record(record)}


@router.post("/{plugin_id}/disable")
def disable_plugin(plugin_id: str, request: PluginDisableRequest, http_request: Request):
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    registry = _registry()
    try:
        _audit("plugin.disable", "requested", plugin_id)
        record = registry.disable(plugin_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plugin not found.") from exc
    except PluginRegistryError as exc:
        raise HTTPException(status_code=503, detail="Plugin registry integrity could not be established.") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Plugin disable could not be completed safely.") from exc
    plugin_runtime = getattr(http_request.app.state, "plugin_runtime", None)
    if plugin_runtime is not None:
        plugin_runtime.reconcile_handlers()
    try:
        _audit("plugin.disable", "completed", plugin_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "plugin_disable_audit_failed", "side_effect_may_have_occurred": True},
        ) from exc
    return {"success": True, "plugin": _safe_record(record)}
