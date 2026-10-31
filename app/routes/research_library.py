from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services.research.research_library_service import ResearchLibraryService

router = APIRouter(prefix="/research-library")


class ResearchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=2000)
    summary: str = Field(default="", max_length=10000)
    project_id: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=20)


@router.post("", status_code=201)
def add_research(request: ResearchCreateRequest):
    try:
        item = ResearchLibraryService().add(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "research": item}


@router.get("/recent")
def recent_research(limit: int = Query(default=20, ge=0, le=100)):
    try:
        items = ResearchLibraryService().list_recent(limit)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Research library is unavailable") from exc
    return {"success": True, "count": len(items), "items": items}


@router.get("/summary")
def research_summary():
    try:
        return {"success": True, "summary": ResearchLibraryService().summary()}
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Research library is unavailable") from exc


@router.get("/search")
def search_research(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=50, ge=0, le=100)):
    try:
        items = ResearchLibraryService().search(q.strip(), limit=limit)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Research library is unavailable") from exc
    return {"success": True, "query": q.strip(), "count": len(items), "items": items}
