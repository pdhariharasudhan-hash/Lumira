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


@router.get("/search")
def search_research(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=50, ge=0, le=100)):
    try:
        items = ResearchLibraryService().search(q.strip(), limit=limit)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Research library is unavailable") from exc
    return {"success": True, "query": q.strip(), "count": len(items), "items": items}

@router.get("/recent")
def recent_research(limit: int = Query(default=20, ge=0, le=100)):
    try:
        items = ResearchLibraryService().list_recent(limit)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Research library is unavailable") from exc
    return {"success": True, "count": len(items), "items": items}



@router.get("/tags")
def research_tags():
    try:
        return {"success": True, "tags": ResearchLibraryService().tag_counts()}
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Research library is unavailable") from exc


@router.get("/summary")
def research_summary():
    try:
        return {"success": True, "summary": ResearchLibraryService().summary()}
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Research library is unavailable") from exc


@router.get("/trends")
def research_trends(limit: int = Query(default=1000, ge=0, le=1000)):
    try:
        return {"success": True, "trends": ResearchLibraryService().trend_analysis(limit)}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Research library is unavailable") from exc


@router.get("/graph")
def research_graph(limit: int = Query(default=1000, ge=0, le=1000)):
    try:
        return {"success": True, "graph": ResearchLibraryService().knowledge_graph(limit)}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Research library is unavailable") from exc


@router.get("/{research_id}")
def get_research(research_id: str):
    try:
        item = ResearchLibraryService().get(research_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="research item not found")
    return {"success": True, "research": item}


class ResearchUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=300)
    source: str | None = Field(default=None, min_length=1, max_length=2000)
    summary: str | None = Field(default=None, max_length=10000)
    project_id: str | None = Field(default=None, max_length=200)
    tags: list[str] | None = Field(default=None, max_length=20)


@router.patch("/{research_id}")
def update_research(research_id: str, request: ResearchUpdateRequest):
    try:
        item = ResearchLibraryService().update(research_id, **request.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="research item not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "research": item}


@router.delete("/{research_id}")
def delete_research(research_id: str):
    try:
        deleted = ResearchLibraryService().remove(research_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="research item not found")
    return {"success": True, "deleted": True, "research_id": research_id}





