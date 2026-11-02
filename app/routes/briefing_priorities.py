from fastapi import APIRouter
from app.services.briefing.personal_briefing_service import PersonalBriefingService
from app.services.briefing.briefing_priority_service import BriefingPriorityService

router = APIRouter(prefix="/briefing", tags=["briefing"])
_briefing = PersonalBriefingService()
_priority = BriefingPriorityService()

@router.get("/priorities")
def briefing_priorities():
    return _priority.prioritize(_briefing.build())
