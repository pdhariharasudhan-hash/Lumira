from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService,
    SUPPORTED_ARTIFACT_TYPES,
)

router = APIRouter()


class ArtifactCreateRequest(BaseModel):
    type: str
    content: str
    source: str = "api"
    extension: str = Field(default="txt", pattern=r"^[A-Za-z0-9]{1,12}$")


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


@router.get("/artifacts")
def list_artifacts(artifact_type: str | None = None, q: str | None = None):
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