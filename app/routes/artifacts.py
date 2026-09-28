from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import base64
import binascii

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService,
    SUPPORTED_ARTIFACT_TYPES,
)

router = APIRouter()


class ArtifactCreateRequest(BaseModel):
    type: str
    content: str = Field(max_length=ArtifactManagerService.MAX_CONTENT_LENGTH)
    source: str = Field(default="api", max_length=500)
    extension: str = Field(default="txt", pattern=r"^[A-Za-z0-9]{1,12}$")


class BinaryArtifactCreateRequest(BaseModel):
    type: str
    content_base64: str = Field(min_length=4, max_length=33_333_336)
    source: str = Field(default="api", max_length=500)
    extension: str = Field(pattern=r"^[A-Za-z0-9]{1,12}$")


def _manager() -> ArtifactManagerService:
    return ArtifactManagerService()


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
    return {"success": True, "artifact": artifact}


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
    return {"success": True, "artifact": artifact}


@router.get("/artifacts")
def list_artifacts(artifact_type: str | None = None, q: str | None = Query(default=None, max_length=500)):
    manager = _manager()
    if artifact_type and artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported artifact type: {artifact_type}",
        )
    artifacts = manager.get_all_artifacts()
    if artifact_type:
        artifacts = [
            artifact
            for artifact in artifacts
            if artifact.get("type") == artifact_type
        ]
    if q:
        query = q.lower()
        artifacts = [
            artifact
            for artifact in artifacts
            if query in " ".join(str(value) for value in artifact.values()).lower()
        ]
    return {"success": True, "artifacts": artifacts}


@router.get("/artifacts/stats")
def artifact_stats():
    return {"success": True, "stats": _manager().stats()}


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
    artifact = _manager().get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"success": True, "artifact": artifact}


@router.delete("/artifacts/{artifact_id}")
def delete_artifact(artifact_id: str):
    try:
        deleted = _manager().delete_artifact(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"success": True, "artifact_id": artifact_id}
