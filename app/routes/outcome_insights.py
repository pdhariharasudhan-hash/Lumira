from fastapi import APIRouter, Query
from app.services.system.outcome_insights_service import OutcomeInsightsService

router = APIRouter(prefix='/system/outcomes', tags=['outcomes'])
_service = OutcomeInsightsService()

@router.get('/summary')
def outcome_summary(limit: int = Query(100, ge=1, le=500)):
    return _service.summary(limit)
