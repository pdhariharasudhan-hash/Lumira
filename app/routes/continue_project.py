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
    version: str = Field(pattern=r"^v[1-9][0-9]{0,8}$")
    instruction: str = Field(min_length=1, max_length=10000)


@router.post(
    "/continue_project"
)
def continue_project(
    request: ContinueRequest
):

    lifecycle = (
        ProjectLifecycleService()
    )

    existing = (

        lifecycle
        .get_project_version(

            request.project,
            request.version
        )
    )

    if not existing["success"]:

        return existing

    metadata = existing["data"].get("metadata")
    if not isinstance(metadata, dict):
        return {"success": False, "status": "reject", "error": "Project metadata is missing or invalid."}

    result = (

        lifecycle
        .continue_project(

            metadata=
            metadata,

            instruction=
            request.instruction
        )
    )

    if not result.get("success"):
        return {
            "success": False,
            "status": result.get("status", "reject"),
            "previous": f"{request.project}/{request.version}",
            "error": result.get("error", "Project continuation did not complete."),
            "builder": result.get("builder"),
            "execution": result.get("execution"),
            "validation": result.get("validation"),
        }

    return {

        "success":
        result["success"],

        "previous":
        f"{request.project}/{request.version}",

        "saved_to":
        result["saved_to"],

        "new_idea":
        result["new_idea"],

        "instructions":
        result["instructions"],

        "features":
        result["features"]
    }
