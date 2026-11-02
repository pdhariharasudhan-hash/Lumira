from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.research.research_comparison_service import ResearchComparisonService

router = APIRouter(prefix="/research", tags=["Research"])
service = ResearchComparisonService()

class ResearchCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_ids: list[str] = Field(min_length=2, max_length=10)

@router.post("/compare")
def compare(request: ResearchCompareRequest):
    try: return {"success": True, "comparison": service.compare(request.research_ids)}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
