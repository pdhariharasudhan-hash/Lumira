from fastapi import APIRouter
from app.services.tasks.task_insights_service import TaskInsightsService

router = APIRouter(prefix="/quick-tasks", tags=["quick-tasks"])
_insights = TaskInsightsService()

@router.get("/insights")
def task_insights():
    return _insights.summary()
