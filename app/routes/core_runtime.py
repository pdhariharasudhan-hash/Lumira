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
