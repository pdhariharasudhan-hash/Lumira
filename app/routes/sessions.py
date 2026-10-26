from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.sessions.session_manager_service import SessionManagerService

router = APIRouter()


class SessionCreateRequest(BaseModel):
    workspace_id: str = Field(default="default", min_length=1, max_length=100)
    project_id: str | None = Field(default=None, max_length=100)


class SessionContextUpdateRequest(BaseModel):
    active_project: str | None = Field(default=None, max_length=100)
    active_version: str | None = Field(default=None, max_length=100)
    active_mode: str | None = Field(default=None, max_length=50)
    current_goal: str | None = Field(default=None, max_length=4000)
    goal_id: str | None = Field(default=None, max_length=128)
    project_id: str | None = Field(default=None, max_length=100)


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error).strip("'"))
    if isinstance(error, ValueError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=500, detail="Session persistence failed safely")


@router.post("/sessions")
def create_session(request: SessionCreateRequest):
    return SessionManagerService().create_session(
        workspace_id=request.workspace_id,
        project_id=request.project_id,
    )


@router.get("/sessions")
def list_sessions(limit: int = Query(default=50, ge=0, le=200)):
    try:
        return {"sessions": SessionManagerService().list_sessions(limit)}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    try:
        session = SessionManagerService().get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        return session
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/resume")
def resume_session(session_id: str):
    try:
        return SessionManagerService().resume_session(session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/pause")
def pause_session(session_id: str):
    try:
        return SessionManagerService().pause_session(session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/close")
def close_session(session_id: str):
    try:
        return SessionManagerService().close_session(session_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/recovery-snapshot")
def create_recovery_snapshot(session_id: str):
    """Create a compact recovery package for resuming this session later."""
    sessions = SessionManagerService()
    try:
        snapshot = sessions.snapshot_context(session_id)
        session = sessions.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        pending = snapshot.get("pending_tasks", [])
        return {
            "success": True,
            "session_id": session_id,
            "status": session.get("status"),
            "context_snapshot": snapshot,
            "recent_messages": session.get("recent_messages", [])[-10:],
            "resume_summary": {
                "active_project": snapshot.get("active_project"),
                "active_version": snapshot.get("active_version"),
                "active_mode": snapshot.get("active_mode"),
                "current_goal": snapshot.get("current_goal"),
                "goal_id": snapshot.get("goal_id"),
                "pending_task_count": len(pending),
                "pending_task_titles": [item.get("title") for item in pending[:10]],
                "workflow_count": len(snapshot.get("workflows", [])),
                "blocker_count": len(snapshot.get("blockers", [])),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@router.patch("/sessions/{session_id}/context")
def update_session_context(session_id: str, request: SessionContextUpdateRequest):
    values = request.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="at least one context field is required")
    try:
        return SessionManagerService().update_context(session_id, **values)
    except Exception as exc:
        raise _http_error(exc) from exc
