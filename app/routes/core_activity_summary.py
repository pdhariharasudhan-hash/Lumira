from fastapi import APIRouter, Query
from app.services.system.core_activity_summary_service import CoreActivitySummaryService

router = APIRouter(prefix='/system/activity', tags=['system-activity'])
_service = CoreActivitySummaryService()

@router.get('')
def activity_summary(limit: int = Query(100, ge=1, le=500)):
    return _service.summary(limit)
