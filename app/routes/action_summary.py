from fastapi import APIRouter, Query
from app.services.work_items.next_action_service import NextActionService
from app.services.work_items.action_summary_service import ActionSummaryService

router = APIRouter(prefix='/actions', tags=['actions'])
_service = ActionSummaryService(NextActionService())

@router.get('/summary')
def action_summary(project_id: str | None = Query(default=None, max_length=128), limit: int = Query(5, ge=1, le=50)):
    return _service.summary(project_id, limit)
