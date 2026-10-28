from fastapi import APIRouter, HTTPException, Query
from typing import Annotated
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import base64
import binascii

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService,
    SUPPORTED_ARTIFACT_TYPES,
)
from app.services.artifacts.artifact_library_query_service import ArtifactLibraryQueryService

router = APIRouter()


class ArtifactCreateRequest(BaseModel):
    type: str
    content: str = Field(max_length=ArtifactManagerService.MAX_CONTENT_LENGTH)
    source: str = Field(default="api", max_length=500)
    extension: str = Field(default="txt", pattern=r"^[A-Za-z0-9]{1,12}$")


class ArtifactLinkRequest(BaseModel):
    target_artifact_id: str = Field(min_length=1, max_length=128)
    relation: str = Field(default="related_to", pattern=r"^[a-z][a-z0-9_-]{0,39}$")


class BinaryArtifactCreateRequest(BaseModel):
    type: str
    content_base64: str = Field(min_length=4, max_length=33_333_336)
    source: str = Field(default="api", max_length=500)
    extension: str = Field(pattern=r"^[A-Za-z0-9]{1,12}$")


def _manager() -> ArtifactManagerService:
    return ArtifactManagerService()


def _public_artifact(record: dict) -> dict:
    """Return artifact metadata without exposing internal filesystem paths."""
    return {key: value for key, value in record.items() if key != "file"}


@router.post("/artifacts", status_code=201)
def create_artifact(request: ArtifactCreateRequest):
    if request.type not in SUPPORTED_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported artifact type: {request.type}",
        )
    try:
        artifact = _manager().create_artifact(
            artifact_type=request.type,
            content=request.content,
            source=request.source,
            extension=request.extension,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "artifact": _public_artifact(artifact)}


@router.post("/artifacts/binary", status_code=201)
def create_binary_artifact(request: BinaryArtifactCreateRequest):
    if request.type not in {"audio", "images", "video", "pdf", "generated_files"}:
        raise HTTPException(status_code=400, detail="Unsupported binary artifact type")
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="content_base64 must be valid Base64") from exc
    if not content or len(content) > ArtifactManagerService.MAX_BINARY_CONTENT_BYTES:
        raise HTTPException(status_code=413, detail="Binary artifact exceeds the 25 MB limit")
    extension = request.extension.lower()
    if request.type == "pdf" and (extension != "pdf" or not content.startswith(b"%PDF-")):
        raise HTTPException(status_code=422, detail="PDF artifacts must contain a valid PDF signature")
    if request.type == "video":
        valid_video = (extension == "mp4" and len(content) >= 12 and content[4:8] == b"ftyp") or (extension == "webm" and content.startswith(b"\x1aE\xdf\xa3"))
        if not valid_video:
            raise HTTPException(status_code=422, detail="Video artifacts must be MP4 or WebM content")
    try:
        artifact = _manager().create_binary_artifact(request.type, content, request.source, extension)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "artifact": _public_artifact(artifact)}


@router.get("/artifacts")
def list_artifacts(
    artifact_type: str | None = None,
    q: Annotated[str | None, Query(max_length=500)] = None,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
):
    try:
        result = ArtifactLibraryQueryService(_manager()).list_artifacts(
            artifact_type=artifact_type,
            query=q,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, **result}


@router.get("/artifacts/stats")
def artifact_stats():
    manager = _manager()
    stats = manager.stats()
    artifacts = manager.get_all_artifacts()
    stats["archived"] = sum(1 for item in artifacts if item.get("archived", False))
    stats["active"] = len(artifacts) - stats["archived"]
    return {"success": True, "stats": stats}


@router.get("/artifacts/{artifact_id}/content")
def get_artifact_content(artifact_id: str):
    manager = _manager()
    try:
        path = manager.get_artifact_path(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(path)


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    manager = _manager()
    artifact = manager.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    try:
        content_path = manager.get_artifact_path(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="artifact content path is invalid") from exc
    public_artifact = _public_artifact(artifact)
    # Expose availability, never the local filesystem path itself.
    public_artifact["content_available"] = content_path is not None and content_path.is_file()
    return {"success": True, "artifact": public_artifact}


@router.post("/artifacts/{artifact_id}/links", status_code=201)
def link_artifact(artifact_id: str, request: ArtifactLinkRequest):
    manager = _manager()
    try:
        result = manager.link_artifacts(
            source_id=artifact_id,
            target_id=request.target_artifact_id,
            relation=request.relation,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="source or target artifact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "source_artifact_id": artifact_id, **result}


@router.delete("/artifacts/{artifact_id}/links")
def unlink_artifact(
    artifact_id: str,
    target_artifact_id: Annotated[str, Query(min_length=1, max_length=128)],
    relation: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_-]{0,39}$")] = "related_to",
):
    manager = _manager()
    try:
        result = manager.unlink_artifacts(
            source_id=artifact_id,
            target_id=target_artifact_id,
            relation=relation,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="source or target artifact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "source_artifact_id": artifact_id, **result}


@router.get("/artifacts/{artifact_id}/links")
def get_artifact_links(artifact_id: str):
    manager = _manager()
    if manager.get_artifact(artifact_id) is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"success": True, **manager.get_artifact_links(artifact_id)}


@router.post("/artifacts/{artifact_id}/archive")
def archive_artifact(artifact_id: str):
    try:
        archived = _manager().archive_artifact(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not archived:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"success": True, "artifact_id": artifact_id, "archived": True}


@router.post("/artifacts/{artifact_id}/restore")
def restore_artifact(artifact_id: str):
    try:
        restored = _manager().restore_artifact(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not restored:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"success": True, "artifact_id": artifact_id, "archived": False}


@router.delete("/artifacts/{artifact_id}")
def delete_artifact(artifact_id: str):
    try:
        deleted = _manager().delete_artifact(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"success": True, "artifact_id": artifact_id}
