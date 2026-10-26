from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.workspace.project_preview_service import ProjectPreviewService

router = APIRouter()
service = ProjectPreviewService()


class PreviewRequest(BaseModel):
    project: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r"^v[1-9][0-9]{0,8}$")
    url: str = Field(min_length=8, max_length=500)


@router.get("/projects/{project}/{version}/preview")
def preview_get(project: str, version: str):
    return service.get(project, version)


@router.post("/projects/{project}/{version}/preview")
def preview_register(project: str, version: str, payload: PreviewRequest):
    if payload.project != project or payload.version != version:
        return {"success": False, "code": "path_mismatch", "message": "Project path and payload must match."}
    return service.register(project, version, payload.url)


@router.post("/projects/{project}/{version}/preview/stop")
def preview_stop(project: str, version: str):
    return service.stop(project, version)
