from fastapi import APIRouter, Query
from app.services.work_items.next_action_service import NextActionService
from app.services.work_items.blocker_queue_service import BlockerQueueService
from app.services.system.execution_readiness_service import ExecutionReadinessService
from app.services.system.core_attention_service import CoreAttentionService
from app.services.briefing.personal_briefing_service import PersonalBriefingService
from app.services.briefing.briefing_priority_service import BriefingPriorityService
from app.services.system.core_state_service import CoreStateService
from app.services.system.decision_snapshot_service import DecisionSnapshotService
from app.services.system.progress_signal_service import ProgressSignalService

router = APIRouter(prefix='/system/core-intelligence', tags=['core-intelligence'])
_readiness = ExecutionReadinessService(NextActionService(), BlockerQueueService())
_attention = CoreAttentionService(PersonalBriefingService(), BriefingPriorityService())
_state = CoreStateService(_readiness, _attention)
_decision = DecisionSnapshotService(_readiness, _attention)
_progress = ProgressSignalService(NextActionService(), BlockerQueueService())

@router.get('/state')
def state(project_id: str | None = Query(default=None, max_length=128)):
    return _state.state(project_id)

@router.get('/decision')
def decision(project_id: str | None = Query(default=None, max_length=128)):
    return _decision.snapshot(project_id)

@router.get('/progress')
def progress(project_id: str | None = Query(default=None, max_length=128)):
    return _progress.signal(project_id)
