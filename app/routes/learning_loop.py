from fastapi import APIRouter, Query
from app.services.memory.memory_service import MemoryService
from app.services.system.outcome_pattern_service import OutcomePatternService
from app.services.system.learning_recommendation_service import LearningRecommendationService
from app.services.system.learning_loop_status_service import LearningLoopStatusService
from app.services.system.failure_guard_service import FailureGuardService

router = APIRouter(prefix="/system/learning", tags=["learning-loop"])
_memory = MemoryService()
_pattern = OutcomePatternService(_memory)
_recommendation = LearningRecommendationService(_pattern)
_status = LearningLoopStatusService(_pattern, _recommendation)
_guard = FailureGuardService(_pattern)

@router.get("/status")
def learning_status(project_id: str | None = Query(default=None, max_length=128)):
    return _status.status(project_id)

@router.get("/failure-guard")
def failure_guard(project_id: str | None = Query(default=None, max_length=128)):
    return _guard.evaluate(project_id)
