from fastapi import APIRouter, Query
from app.services.work_items.next_action_service import NextActionService
from app.services.work_items.blocker_queue_service import BlockerQueueService
from app.services.system.execution_readiness_service import ExecutionReadinessService
from app.services.system.outcome_insights_service import OutcomeInsightsService
from app.services.system.execution_review_service import ExecutionReviewService

router = APIRouter(prefix='/system/execution', tags=['execution-review'])
_readiness = ExecutionReadinessService(NextActionService(), BlockerQueueService())
_service = ExecutionReviewService(_readiness, OutcomeInsightsService())

@router.get('/review')
def execution_review(project_id: str | None = Query(default=None, max_length=128)):
    return _service.review(project_id)
