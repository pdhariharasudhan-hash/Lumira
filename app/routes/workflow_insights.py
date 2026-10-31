from fastapi import APIRouter, Query
from app.services.work_items.workflow_insights_service import WorkflowInsightsService

router = APIRouter(prefix="/workflows", tags=["workflows"])
_service = WorkflowInsightsService()

@router.get("/insights")
def workflow_insights(project_id: str | None = Query(default=None, max_length=128), goal_id: str | None = Query(default=None, max_length=128)):
    return _service.summary(project_id, goal_id)
