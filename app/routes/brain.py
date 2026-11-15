from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.schemas.common import BrainCapabilityRequest, GenericInput
from app.services.response.response_service import build_structured_response
from app.services.brain.brain_request import BrainRequest
from app.services.brain.brain_service import BrainService
from app.services.sessions.session_manager_service import SessionManagerService
from app.services.brain.public_brain_view import public_brain_state, public_brain_trace
from app.services.brain.execution_control import BrainExecutionControlRegistry

router = APIRouter()


class BrainPluginExecutionRequest(BaseModel):
    """A plugin invocation that must pass the Main Brain verification gate."""

    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=10_000)
    session_id: str = Field(min_length=1, max_length=256)
    confirm: StrictBool
    arguments: dict = Field(default_factory=dict)
    approval_id: str | None = Field(default=None, max_length=128)
    autonomous: StrictBool = False


@router.post("/brain/cancel/{session_id}")
def cancel_brain_execution(session_id: str):
    """Request cooperative cancellation of active Brain runs in one session."""
    if not session_id.strip() or len(session_id) > 256:
        raise HTTPException(status_code=422, detail="invalid session_id")
    cancelled = BrainExecutionControlRegistry.cancel_for_session(session_id)
    return {
        "success": cancelled > 0,
        "session_id": session_id,
        "cancelled_executions": cancelled,
        "message": "Cancellation requested" if cancelled else "No active Brain execution found",
    }


def main_brain_flow(content: str, session_id: str | None = None, workspace_id: str = "default", project_id: str | None = None) -> dict:
    response = BrainService().execute(
        BrainRequest(
            message=content.strip(),
            session_id=session_id or "",
            workspace=workspace_id,
            project=project_id,
        )
    )
    return {
        "stage": "complete" if response.success else "failed",
        "status": "ready_for_build" if response.success else "failed",
        "state": public_brain_state(response.state),
        "trace": public_brain_trace(response.trace),
        "error": response.error,
    }


@router.post("/brain")
def brain_endpoint(payload: GenericInput):
    content = payload.input.strip()

    if not content:
        return build_structured_response(
            endpoint="brain",
            status="error",
            data={"stage": "failed", "status": "invalid_input", "error": "input cannot be empty"},
        )

    result = main_brain_flow(
        content,
        session_id=payload.session_id,
        workspace_id=payload.workspace_id,
        project_id=payload.project_id,
    )

    execution_context = (result.get("state") or {}).get("execution_context", {})
    session_id = execution_context.get("session_id")
    if session_id:
        SessionManagerService().append_message(
            session_id,
            "assistant",
            "Cognitive pipeline completed." if result["stage"] == "complete" else "Cognitive pipeline failed.",
            metadata={
                "execution_id": execution_context.get("execution_id"),
                "success": result["stage"] == "complete",
            },
        )

    return build_structured_response(
        endpoint="brain",
        status="ok" if result["stage"] == "complete" else "error",
        data=result
    )


@router.post("/brain/execute")
def brain_execute_capability(payload: BrainCapabilityRequest):
    """Run one explicitly requested capability through the verified Brain gate."""
    response = BrainService().execute(
        BrainRequest(
            message=payload.message.strip(),
            session_id=payload.session_id or "",
            workspace=payload.workspace_id,
            project=payload.project_id,
            metadata={
                "execute_capability": payload.capability.strip(),
                "capability_payload": payload.payload,
                "autonomous": payload.autonomous,
            },
        )
    )
    return build_structured_response(
        endpoint="brain.execute",
        status="ok" if response.success else "error",
        data={
            "success": response.success,
            "error": response.error,
            "state": public_brain_state(response.state),
            "trace": public_brain_trace(response.trace),
        },
    )


@router.get("/brain/core-context")
def brain_core_context(
    session_id: str | None = None,
    project_id: str | None = None,
    goal_id: str | None = None,
):
    from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
    return CoreRuntimeBridgeService().context(session_id, project_id, goal_id)


@router.get("/brain/state/{session_id}")
def get_brain_state(session_id: str):
    try:
        session = SessionManagerService().get_session(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Session state could not be loaded safely") from exc
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": session_id,
        "cognitive_state": session.get("cognitive_state"),
        "context_snapshot": session.get("context_snapshots", [])[-1:]
        or [],
    }


@router.post("/brain/plugins/{plugin_id}/capabilities/{capability}/execute")
async def brain_execute_plugin_capability(
    plugin_id: str,
    capability: str,
    payload: BrainPluginExecutionRequest,
    request: Request,
):
    """Run the cognitive verification pipeline before a trusted plugin handler.

    Plugin code is never loaded here. The app-owned runtime must already have
    an explicitly registered handler, and it rechecks plugin grants and audit
    policy immediately before executing it.
    """
    if payload.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    runtime = getattr(request.app.state, "plugin_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="Plugin runtime is unavailable.")
    try:
        if SessionManagerService().get_session(payload.session_id) is None:
            raise HTTPException(status_code=404, detail="session not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Session authorization state is unavailable.") from exc

    brain_response = await run_in_threadpool(
        BrainService().execute,
        BrainRequest(
            message=(
                f"{payload.message.strip()}\n\n"
                f"Requested trusted plugin capability: {plugin_id}.{capability}"
            ),
            session_id=payload.session_id,
            metadata={"requested_plugin_execution": {"plugin_id": plugin_id, "capability": capability}},
        ),
    )
    if brain_response.success is not True:
        return build_structured_response(
            endpoint="brain.plugin.execute",
            status="error",
            data={
                "success": False,
                "code": "brain_validation_failed",
                "message": "Main Brain processing failed; plugin execution was not started.",
                "brain_error": brain_response.error,
            },
        )

    verification = getattr(brain_response.state, "verification_result", None)
    if not isinstance(verification, dict) or verification.get("ready_for_execution") is not True:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "brain_verification_rejected",
                "message": "Main Brain did not explicitly verify this request for execution.",
                "plugin_execution_started": False,
            },
        )

    result = await runtime.execute(
        plugin_id,
        capability,
        payload.arguments,
        session_id=payload.session_id,
        approval_id=payload.approval_id,
        autonomous=payload.autonomous,
    )
    if result.get("success") is not True:
        code = result.get("code")
        status_code = (
            503 if code in {"security_audit_unavailable", "execution_outcome_audit_failed", "plugin_registry_unavailable"}
            else 403 if code in {"plugin_permission_unavailable", "permission_denied", "autonomous_permission_required", "autonomous_permission_state_unavailable"}
            else 404 if code in {"plugin_not_found", "plugin_handler_not_found"}
            else 409 if code in {"approval_required", "approval_missing_or_consumed", "approval_expired", "approval_context_mismatch", "tool_capacity_busy"}
            else 422
        )
        raise HTTPException(status_code=status_code, detail={**result, "brain_gate": "passed"})

    return build_structured_response(
        endpoint="brain.plugin.execute",
        status="ok",
        data={
            "success": True,
            "brain_gate": "passed",
            "brain_execution_id": getattr(getattr(brain_response.state, "execution_context", None), "execution_id", None),
            "plugin_id": plugin_id,
            "capability": capability,
            "execution": result,
        },
    )

@router.get("/brain/plugins/capabilities")
def brain_list_available_plugin_capabilities(request: Request):
    """Expose only currently bound, approved plugin handlers to Brain clients."""
    runtime = getattr(request.app.state, "plugin_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="Plugin runtime is unavailable.")
    try:
        handlers = runtime.list_handlers()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Plugin runtime state could not be reconciled.") from exc
    return {
        "success": True,
        "capabilities": [
            {
                "plugin_id": item["plugin_id"],
                "capability": item["capability"],
                "required_permissions": item["required_permissions"],
                "tool_manifest": item["tool_manifest"],
                "runtime": item["runtime"],
                "execution_endpoint": (
                    f"/brain/plugins/{item['plugin_id']}/capabilities/{item['capability']}/execute"
                ),
                "requires_owner_confirmation": True,
            }
            for item in handlers
        ],
        "count": len(handlers),
        "discovery_scope": "currently_bound_trusted_handlers_only",
        "untrusted_manifest_code_executed": False,
    }
