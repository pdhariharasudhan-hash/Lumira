from fastapi import APIRouter
from pathlib import Path
from app.services.projects.project_paths import resolve_project_path

router = APIRouter()


@router.get(
    "/projects/{project}"
)
def get_versions(
    project: str
):

    project_path = resolve_project_path(project)

    if project_path is None or not project_path.is_dir():

        return {

            "success":
            False,

            "message":
            "Project not found"
        }


    versions = []


    for version in project_path.iterdir():

        if version.is_dir() and resolve_project_path(project, version.name) == version.resolve():

            versions.append(
                version.name
            )


    versions.sort(key=lambda value: int(value[1:]))


    return {

        "success":
        True,

        "project":
        project,

        "versions":
        versions
    }
