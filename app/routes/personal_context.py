from fastapi import APIRouter, Query
from app.services.personal_context.personal_context_service import PersonalContextService

router = APIRouter(prefix="/personal-context")

@router.get("")
def personal_context(q: str = Query(default="", max_length=500), note_limit: int = Query(default=10, ge=0, le=50)):
    snapshot = PersonalContextService().snapshot(q, note_limit)
    return {"success": True, "context": snapshot}


@router.get("/core-overview")
def personal_context_core_overview():
    from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
    return CoreRuntimeBridgeService().overview()
