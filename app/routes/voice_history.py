from fastapi import APIRouter, HTTPException, Query
from app.services.voice.voice_history_service import VoiceHistoryService

router = APIRouter(prefix="/voice/history", tags=["Voice History"])
service = VoiceHistoryService()

@router.get("")
def history(limit: int = Query(default=100, ge=0, le=200)):
    try:
        return {"success": True, "items": service.list(limit)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
