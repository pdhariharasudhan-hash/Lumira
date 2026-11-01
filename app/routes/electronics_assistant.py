from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.inventor.electronics_assistant_service import ElectronicsAssistantService

router = APIRouter(prefix="/electronics", tags=["Electronics Assistant"])
service = ElectronicsAssistantService()

class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=32)
    objective: str = Field(min_length=1, max_length=5000)
    components: list[str] = Field(default_factory=list, max_length=100)

class BomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    components: list[str] = Field(default_factory=list, max_length=100)

@router.post("/plan")
def create_plan(request: PlanRequest):
    try: return {"success": True, "plan": service.create_plan(**request.model_dump())}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/bom-template")
def bom_template(request: BomRequest):
    try: return {"success": True, "items": service.bom_template(request.components)}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
