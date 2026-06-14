from fastapi import APIRouter
from pydantic import BaseModel

from app.routes.project_details import (
    get_project
)

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

    existing = get_project(
        request.project,
        request.version
    )

    if not existing["success"]:

        return existing

    metadata = (
        existing["data"]
        ["metadata"]
    )

    result = (

        ProjectLifecycleService()
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