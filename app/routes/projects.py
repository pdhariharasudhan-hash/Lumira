from fastapi import APIRouter

from app.services.project_discovery_service import (
    ProjectDiscoveryService
)

router = APIRouter()


@router.get(
    "/projects"
)
def get_projects():

    projects = (
        ProjectDiscoveryService()
        .get_projects()
    )

    return {

        "success":
        True,

        "count":
        len(
            projects
        ),

        "projects":
        projects
    }