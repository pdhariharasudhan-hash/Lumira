from fastapi import APIRouter
from pydantic import BaseModel

from app.services.lifecycle.project_lifecycle_service import (
    ProjectLifecycleService
)


router = APIRouter()


class ContinueRequest(
    BaseModel
):
    project: str
    version: str
    instruction: str


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

    metadata = (
        existing["data"]
        ["metadata"]
    )

    result = (

        lifecycle
        .continue_project(

            metadata=
            metadata,

            instruction=
            request.instruction
        )
    )

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