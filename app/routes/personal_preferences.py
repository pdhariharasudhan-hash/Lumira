from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.personal.preference_profile_service import PreferenceProfileService

router = APIRouter(prefix="/personal-preferences", tags=["Personal Preferences"])
service = PreferenceProfileService()

class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(max_length=5000)

@router.get("")
def list_preferences(): return {"success": True, "preferences": service.list()}

@router.put("")
def set_preference(request: PreferenceUpdate):
    try: return {"success": True, "preference": service.set(request.key, request.value)}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.delete("/{key}")
def remove_preference(key: str):
    try:
        if not service.remove(key): raise HTTPException(status_code=404, detail="preference not found")
        return {"success": True, "deleted": True}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
