from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.lifecycle.project_lifecycle_service import (
    ProjectLifecycleService
)


router = APIRouter()


class ContinueRequest(
    BaseModel
):
    project: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    version: str | None = Field(default=None, pattern=r"^v[1-9][0-9]{0,8}$")
    instruction: str = Field(min_length=1, max_length=1500)


@router.post(
    "/continue_project"
)
def continue_project(
    request: ContinueRequest
):

    lifecycle = (
        ProjectLifecycleService()
    )

    result = (
        lifecycle.continue_project_version(
            request.project,
            request.version,
            request.instruction,
        )
        if request.version
        else lifecycle.continue_latest_project(
            request.project,
            request.instruction,
        )
    )

    if not result.get("success"):
        return {
            "success": False,
            "status": result.get("status", "reject"),
            "previous": result.get("previous") or (f"{request.project}/{request.version}" if request.version else request.project),
            "code": result.get("code"),
            "error": result.get("error", "Project continuation did not complete."),
            "builder": result.get("builder"),
            "execution": result.get("execution"),
            "validation": result.get("validation"),
        }

    return {

        "success":
        result["success"],

        "previous":
        result["previous"],

        "saved_to":
        result["saved_to"],

        "new_version":
        result["new_version"],

        "summary":
        result["summary"],

        "changed_files":
        result["changed_files"],

        "new_idea":
        result["new_idea"],

        "instructions":
        result["instructions"],

        "features":
        result["features"]
    }
