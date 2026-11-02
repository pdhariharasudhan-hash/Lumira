from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.modes.ai_mode_service import AIModeService

router = APIRouter(prefix="/ai-mode", tags=["AI Modes"])
service = AIModeService()

class ModeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str = Field(min_length=1, max_length=20)

@router.get("")
def current_mode():
    return {"success": True, **service.get()}

@router.put("")
def set_mode(request: ModeUpdate):
    try: return {"success": True, **service.set(request.mode)}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
