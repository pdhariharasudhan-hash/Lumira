from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.devices.device_profile_service import DeviceProfileService

router = APIRouter(prefix="/device-profiles", tags=["Device Profiles"])
service = DeviceProfileService()

class ProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str = Field(min_length=1, max_length=128)
    device_type: str = Field(min_length=1, max_length=32)
    metadata: dict = Field(default_factory=dict)

@router.post("", status_code=201)
def register(request: ProfileCreate):
    try: return {"success": True, "profile": service.register(**request.model_dump())}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("")
def list_profiles(): return {"success": True, "profiles": service.list()}
