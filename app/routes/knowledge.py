from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from app.services.knowledge.document_ingestion_service import DocumentIngestionService
from app.services.knowledge.knowledge_library_service import KnowledgeLibraryService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Library"])
document_ingestion = DocumentIngestionService()


@router.post("/documents")
async def ingest_document(
    file: UploadFile = File(...),
    project_id: str | None = Query(default=None, max_length=200),
):
    try:
        content = await file.read(DocumentIngestionService.MAX_BYTES + 1)
        result = document_ingestion.ingest(file.filename or "", content, project_id=project_id)
        if not result["success"]:
            status = 413 if result["code"] == "document_too_large" else 422
            raise HTTPException(status_code=status, detail=result)
        return result
    except HTTPException:
        raise
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Document ingestion is unavailable") from exc

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
