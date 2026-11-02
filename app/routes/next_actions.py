from fastapi import APIRouter, Query
from app.services.work_items.next_action_service import NextActionService

router = APIRouter(prefix="/workflows", tags=["workflows"])
_service = NextActionService()

@router.get("/next-actions")
def next_actions(project_id: str | None = Query(default=None, max_length=128), goal_id: str | None = Query(default=None, max_length=128), limit: int = Query(50, ge=1, le=200)):
    return _service.ready(project_id, goal_id, limit)
