from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.inventor.microcontroller_project_service import MicrocontrollerProjectService

router = APIRouter(prefix="/electronics/microcontroller", tags=["Microcontroller Projects"])
service = MicrocontrollerProjectService()

class ScaffoldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: str = Field(min_length=1, max_length=50)
    objective: str = Field(min_length=1, max_length=5000)
    peripherals: list[str] = Field(default_factory=list, max_length=50)

@router.post("/scaffold")
def scaffold(request: ScaffoldRequest):
    try:
        return {"success": True, "project": service.scaffold(**request.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
