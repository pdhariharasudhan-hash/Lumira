from fastapi import APIRouter, HTTPException, Query
from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService

router = APIRouter(prefix="/core/runtime", tags=["Core Runtime Bridge"])

@router.get("/overview")
def runtime_overview():
    return CoreRuntimeBridgeService().overview()

@router.get("/context")
def runtime_context(
    session_id: str | None = Query(default=None, max_length=100),
    project_id: str | None = Query(default=None, max_length=100),
    goal_id: str | None = Query(default=None, max_length=128),
):
    try:
        return CoreRuntimeBridgeService().context(session_id, project_id, goal_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/checkpoint-context")
def runtime_checkpoint_context(workflow_id: str | None = Query(default=None, max_length=128)):
    return CoreRuntimeBridgeService().checkpoint_context(workflow_id)


@router.get("/search-context")
def runtime_search_context(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=20, ge=1, le=100)):
    return CoreRuntimeBridgeService().search_context(q, limit)


@router.get("/agent-context")
def runtime_agent_context(
    task: str = Query(min_length=1, max_length=10000),
    session_id: str | None = Query(default=None, max_length=100),
    project_id: str | None = Query(default=None, max_length=100),
    goal_id: str | None = Query(default=None, max_length=128),
):
    return CoreRuntimeBridgeService().agent_context(task, session_id, project_id, goal_id)
