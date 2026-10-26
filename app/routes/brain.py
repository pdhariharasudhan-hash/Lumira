from fastapi import APIRouter, HTTPException

from app.schemas.common import GenericInput
from app.services.response.response_service import build_structured_response
from app.services.brain.brain_request import BrainRequest
from app.services.brain.brain_service import BrainService
from app.services.sessions.session_manager_service import SessionManagerService
from app.services.brain.public_brain_view import public_brain_state, public_brain_trace

router = APIRouter()


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
