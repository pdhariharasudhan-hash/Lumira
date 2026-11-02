from fastapi import APIRouter, Query
from app.services.goals.goal_insights_service import GoalInsightsService
from app.services.goals.goal_attention_service import GoalAttentionService

router = APIRouter(prefix="/goals", tags=["goals"])
_service = GoalInsightsService()
_attention = GoalAttentionService()

@router.get("/insights")
def goal_insights(project_id: str | None = Query(default=None, max_length=100)):
    return _service.summary(project_id)


@router.get("/attention")
def goal_attention(project_id: str | None = Query(default=None, max_length=100), limit: int = Query(50, ge=1, le=200)):
    return _attention.attention(project_id, limit)
