from fastapi import APIRouter, Query
from app.services.memory.memory_service import MemoryService
from app.services.system.outcome_pattern_service import OutcomePatternService
from app.services.system.learning_recommendation_service import LearningRecommendationService
from app.services.system.adaptive_execution_service import AdaptiveExecutionService
from app.services.system.execution_policy_service import ExecutionPolicyService
from app.services.work_items.next_action_service import NextActionService
from app.services.work_items.blocker_queue_service import BlockerQueueService
from app.services.system.execution_readiness_service import ExecutionReadinessService
from app.services.briefing.personal_briefing_service import PersonalBriefingService
from app.services.briefing.briefing_priority_service import BriefingPriorityService
from app.services.system.core_attention_service import CoreAttentionService
from app.services.system.decision_snapshot_service import DecisionSnapshotService

router = APIRouter(prefix="/system/learning", tags=["learning"])
_memory = MemoryService()
_pattern = OutcomePatternService(_memory)
_learning = LearningRecommendationService(_pattern)
_readiness = ExecutionReadinessService(NextActionService(), BlockerQueueService())
_attention = CoreAttentionService(PersonalBriefingService(), BriefingPriorityService())
_decision = DecisionSnapshotService(_readiness, _attention)
_policy = ExecutionPolicyService(_pattern)
_adaptive = AdaptiveExecutionService(_decision, _learning, _policy)

@router.get("/patterns")
def patterns(project_id: str | None = Query(default=None, max_length=128)):
    return _pattern.summary(project_id)

@router.get("/recommendation")
def recommendation(project_id: str | None = Query(default=None, max_length=128)):
    return _learning.recommend(project_id)

@router.get("/guidance")
def guidance(project_id: str | None = Query(default=None, max_length=128)):
    return _adaptive.guidance(project_id)

@router.get("/policy")
def policy(project_id: str | None = Query(default=None, max_length=128)):
    decision = _decision.snapshot(project_id)
    return _policy.evaluate(decision["recommendation"], project_id)
