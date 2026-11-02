from fastapi import APIRouter, HTTPException
from app.services.system.personal_ai_status_service import PersonalAIStatusService

router = APIRouter(prefix="/system")

@router.get("/overview")
def system_overview():
    try:
        return {"success": True, "overview": PersonalAIStatusService().snapshot()}
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="System overview is temporarily unavailable") from exc
