from fastapi import APIRouter, Query
from app.services.briefing.personal_briefing_service import PersonalBriefingService
from app.services.briefing.briefing_priority_service import BriefingPriorityService
from app.services.system.core_attention_service import CoreAttentionService

router = APIRouter(prefix="/system/attention", tags=["system-attention"])
_service = CoreAttentionService(PersonalBriefingService(), BriefingPriorityService())

@router.get("")
def core_attention(limit: int = Query(5, ge=1, le=20)):
    return _service.snapshot(limit)
