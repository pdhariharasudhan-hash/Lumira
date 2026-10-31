from fastapi import APIRouter
from app.services.briefing.personal_briefing_service import PersonalBriefingService

router = APIRouter(prefix='/briefing', tags=['briefing'])
_service = PersonalBriefingService()

@router.get('')
def get_briefing():
    return _service.build()
