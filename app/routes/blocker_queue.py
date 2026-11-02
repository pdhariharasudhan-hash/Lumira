from fastapi import APIRouter, Query
from app.services.work_items.blocker_queue_service import BlockerQueueService

router = APIRouter(prefix="/blockers", tags=["blockers"])
_service = BlockerQueueService()

@router.get("")
def list_blockers(project_id: str | None = Query(default=None, max_length=128), limit: int = Query(100, ge=1, le=200)):
    return _service.list(project_id, limit)
