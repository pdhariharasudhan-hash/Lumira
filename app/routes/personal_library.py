from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from app.services.knowledge.personal_library_service import PersonalLibraryService

router = APIRouter(prefix="/personal-library", tags=["Personal Library"])
service = PersonalLibraryService()

class LibraryItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    item_type: str = Field(min_length=1, max_length=32)
    content: str = Field(default="", max_length=100000)
    project_id: str | None = Field(default=None, max_length=200)
    source: str | None = Field(default=None, max_length=2000)

@router.post("", status_code=201)
def add_item(request: LibraryItemCreate):
    try: return {"success": True, "item": service.add(**request.model_dump())}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("")
def list_items(item_type: str | None = None, project_id: str | None = None, limit: int = Query(default=100, ge=0, le=200)):
    try: return {"success": True, "items": service.list(item_type, project_id, limit)}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/search")
def search_items(q: str = Query(min_length=1, max_length=500), limit: int = Query(default=50, ge=1, le=200)):
    try: return {"success": True, "items": service.search(q, limit)}
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
