from fastapi import APIRouter
from app.services.briefing.personal_briefing_service import PersonalBriefingService
from app.services.memory.decision_context_service import DecisionContextService

router = APIRouter(prefix='/briefing', tags=['briefing'])
_service = PersonalBriefingService(context_service=DecisionContextService())

@router.get('')
def get_briefing():
    return _service.build()
