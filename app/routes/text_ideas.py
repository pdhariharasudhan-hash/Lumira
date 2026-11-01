from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from app.services.ideas.text_idea_capture_service import TextIdeaCaptureService

router = APIRouter(prefix="/ideas", tags=["Idea Capture"])
service = TextIdeaCaptureService()

class IdeaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=20000)
    title: str | None = Field(default=None, max_length=300)
    category: str = Field(default="general", max_length=32)
    project_id: str | None = Field(default=None, max_length=200)

@router.post("", status_code=201)
def capture(request: IdeaCreate):
    try: return {"success": True, "idea": service.capture(**request.model_dump())}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("")
def list_ideas(q: str | None = Query(default=None, max_length=500), project_id: str | None = Query(default=None, max_length=200), limit: int = Query(default=100, ge=0, le=200)):
    try: return {"success": True, "ideas": service.list(q, project_id, limit)}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
