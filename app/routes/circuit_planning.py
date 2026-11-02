from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.inventor.circuit_planning_service import CircuitPlanningService

router = APIRouter(prefix="/electronics/circuit", tags=["Circuit Planning"])
service = CircuitPlanningService()

class CircuitPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    supply_voltage: float | None = Field(default=None, gt=0, le=1000)
    components: list[str] = Field(min_length=1, max_length=100)
    requirements: list[str] = Field(default_factory=list, max_length=100)

@router.post("/plan")
def create_plan(request: CircuitPlanRequest):
    try:
        return {"success": True, "plan": service.plan(**request.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
