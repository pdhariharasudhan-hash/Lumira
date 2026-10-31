from fastapi import APIRouter, Query
from app.services.memory.decision_context_service import DecisionContextService

router = APIRouter(prefix='/memory/context', tags=['memory-context'])
_service = DecisionContextService()

@router.get('/recent')
def recent_context(limit: int = Query(20, ge=1, le=100)):
    return _service.recent(limit)
