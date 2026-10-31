from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.system.feedback_loop_service import FeedbackLoopService

router = APIRouter(prefix='/system/feedback', tags=['feedback'])
_service = FeedbackLoopService()

class FeedbackRequest(BaseModel):
    action: str = Field(min_length=1, max_length=500)
    outcome: str = Field(pattern='^(success|failure)$')
    project_id: str | None = None
    goal_id: str | None = None

@router.post('')
def record_feedback(request: FeedbackRequest):
    return _service.record(request.action, request.outcome, request.project_id, request.goal_id)
