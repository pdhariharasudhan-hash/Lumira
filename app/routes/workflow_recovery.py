from fastapi import APIRouter, HTTPException, Query
from app.services.work_items.work_item_service import WorkItemService
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
from app.services.system.workflow_recovery_context_service import WorkflowRecoveryContextService
from app.services.system.recovery_target_service import RecoveryTargetService
from app.services.system.workflow_recovery_guidance_service import WorkflowRecoveryGuidanceService

router = APIRouter(prefix="/system/workflow-recovery", tags=["workflow-recovery"])
_memory = MemoryService()
_pattern = OutcomePatternService(_memory)
_learning = LearningRecommendationService(_pattern)
_policy = ExecutionPolicyService(_pattern)
_readiness = ExecutionReadinessService(NextActionService(), BlockerQueueService())
_attention = CoreAttentionService(PersonalBriefingService(), BriefingPriorityService())
_decision = DecisionSnapshotService(_readiness, _attention)
_recovery = RecoveryGuidanceService(
    RecoveryContextService(_decision, _policy, _learning),
    RecoveryPlanService(),
)
_context = WorkflowRecoveryContextService(WorkItemService(), _recovery)
_service = WorkflowRecoveryGuidanceService(_context, RecoveryTargetService())

@router.get("/{workflow_id}")
def workflow_recovery(workflow_id: str, project_id: str | None = Query(default=None, max_length=128)):
    try:
        return _service.guidance(workflow_id, project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Workflow not found")
