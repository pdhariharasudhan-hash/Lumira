from fastapi import APIRouter, Query
from app.services.work_items.blocker_queue_service import BlockerQueueService
from app.services.work_items.blocker_insights_service import BlockerInsightsService

router = APIRouter(prefix="/blockers", tags=["blockers"])
_service = BlockerInsightsService(BlockerQueueService())

@router.get("/insights")
def blocker_insights(project_id: str | None = Query(default=None, max_length=128)):
    return _service.summary(project_id)
