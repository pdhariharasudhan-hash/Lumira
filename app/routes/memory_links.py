from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services.memory.memory_link_service import MemoryLinkService
from app.services.memory.memory_service import MemoryValidationError

router = APIRouter(prefix="/memory/links", tags=["Memory Links"])
service = MemoryLinkService()


class LinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=200)
    target_id: str = Field(min_length=1, max_length=200)
    relation: str = Field(min_length=1, max_length=100)


@router.post("")
def create_link(request: LinkCreate):
    try:
        return {"success": True, "link": service.create(**request.model_dump())}
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("")
def list_links(memory_id: str | None = Query(default=None, max_length=200), limit: int = Query(default=100, ge=0, le=100)):
    try:
        return {"success": True, "links": service.list(memory_id, limit)}
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{memory_id}/related")
def related(memory_id: str, depth: int = Query(default=1, ge=1, le=5), limit: int = Query(default=50, ge=1, le=100)):
    try:
        return {"success": True, **service.related(memory_id, depth, limit)}
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
