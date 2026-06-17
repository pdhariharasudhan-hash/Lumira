from fastapi import APIRouter

from app.services.lifecycle.project_lifecycle_service import (
    ProjectLifecycleService
)

router = APIRouter()


@router.get(
    "/projects/{project}/{version}"
)
def get_project(
    project: str,
    version: str
):

    return (

        ProjectLifecycleService()
        .get_project_version(

            project,
            version
        )
    )