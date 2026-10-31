from fastapi import APIRouter, Query
from app.services.goals.goal_insights_service import GoalInsightsService

router = APIRouter(prefix="/goals", tags=["goals"])
_service = GoalInsightsService()

@router.get("/insights")
def goal_insights(project_id: str | None = Query(default=None, max_length=100)):
    return _service.summary(project_id)
