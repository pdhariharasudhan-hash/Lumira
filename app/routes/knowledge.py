from fastapi import APIRouter, HTTPException, Query
from app.services.knowledge.knowledge_library_service import KnowledgeLibraryService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Library"])

@router.get("/overview")
def knowledge_overview():
    try:
        return {"success": True, "overview": KnowledgeLibraryService().overview()}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Knowledge library is unavailable") from exc

@router.get("/recent")
def recent_knowledge(
    note_limit: int = Query(default=10, ge=0, le=100),
    research_limit: int = Query(default=10, ge=0, le=100),
):
    try:
        return {"success": True, "recent": KnowledgeLibraryService().recent(note_limit, research_limit)}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Knowledge library is unavailable") from exc

@router.get("/digest")
def knowledge_digest(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=10, ge=1, le=50)):
    try:
        return {"success": True, "digest": KnowledgeLibraryService().digest(q, limit)}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Knowledge library is unavailable") from exc


@router.get("/search")
def search_knowledge(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=50, ge=0, le=100)):
    try:
        return {"success": True, **KnowledgeLibraryService().search(q, limit)}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Knowledge library is unavailable") from exc
