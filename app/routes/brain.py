from fastapi import APIRouter, HTTPException

from app.schemas.common import BrainCapabilityRequest, GenericInput
from app.services.response.response_service import build_structured_response
from app.services.brain.brain_request import BrainRequest
from app.services.brain.brain_service import BrainService
from app.services.sessions.session_manager_service import SessionManagerService
from app.services.brain.public_brain_view import public_brain_state, public_brain_trace
from app.services.brain.execution_control import BrainExecutionControlRegistry

router = APIRouter()


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
