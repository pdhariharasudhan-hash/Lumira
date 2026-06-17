from fastapi import APIRouter

from app.services.lifecycle.project_lifecycle_service import (
    ProjectLifecycleService
)

router = APIRouter()


@router.get(
    "/projects"
)
def get_projects():

    return (

        ProjectLifecycleService()
        .list_projects()
    )