from fastapi import APIRouter, Query
from app.services.memory.memory_service import MemoryService
from app.services.system.outcome_pattern_service import OutcomePatternService
from app.services.system.learning_recommendation_service import LearningRecommendationService
from app.services.system.execution_policy_service import ExecutionPolicyService
from app.services.work_items.next_action_service import NextActionService
from app.services.work_items.blocker_queue_service import BlockerQueueService
from app.services.system.execution_readiness_service import ExecutionReadinessService
from app.services.briefing.personal_briefing_service import PersonalBriefingService
from app.services.briefing.briefing_priority_service import BriefingPriorityService
from app.services.system.core_attention_service import CoreAttentionService
from app.services.system.decision_snapshot_service import DecisionSnapshotService
from app.services.system.recovery_context_service import RecoveryContextService
from app.services.system.recovery_plan_service import RecoveryPlanService
from app.services.system.recovery_guidance_service import RecoveryGuidanceService

router = APIRouter(prefix="/system/recovery-intelligence", tags=["recovery-intelligence"])
_memory = MemoryService()
_pattern = OutcomePatternService(_memory)
_learning = LearningRecommendationService(_pattern)
_policy = ExecutionPolicyService(_pattern)
_readiness = ExecutionReadinessService(NextActionService(), BlockerQueueService())
_attention = CoreAttentionService(PersonalBriefingService(), BriefingPriorityService())
_decision = DecisionSnapshotService(_readiness, _attention)
_context = RecoveryContextService(_decision, _policy, _learning)
_guidance = RecoveryGuidanceService(_context, RecoveryPlanService())

@router.get("/context")
def recovery_context(project_id: str | None = Query(default=None, max_length=128)):
    return _context.build(project_id)

@router.get("/guidance")
def recovery_guidance(project_id: str | None = Query(default=None, max_length=128)):
    return _guidance.guidance(project_id)
