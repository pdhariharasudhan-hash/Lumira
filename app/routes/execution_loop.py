from fastapi import APIRouter
from app.services.work_items.next_action_service import NextActionService
from app.services.briefing.personal_briefing_service import PersonalBriefingService
from app.services.briefing.briefing_priority_service import BriefingPriorityService
from app.services.system.core_attention_service import CoreAttentionService
from app.services.work_items.execution_loop_service import ExecutionLoopService

router = APIRouter(prefix="/execution-loop", tags=["execution-loop"])
_attention = CoreAttentionService(PersonalBriefingService(), BriefingPriorityService())
_service = ExecutionLoopService(NextActionService(), _attention)

@router.get("")
def execution_loop():
    return _service.status()
