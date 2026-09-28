from fastapi import APIRouter
from pathlib import Path
from app.services.projects.project_paths import resolve_project_path

router = APIRouter()


@router.get(
    "/projects/{project}/{version}/files"
)
def get_project_files(
    project: str,
    version: str
):

    folder = resolve_project_path(project, version)

    if folder is None or not folder.is_dir():

        return {

            "success":
            False,

            "message":
            "Project version not found"
        }


    files = []


    for file in folder.iterdir():

        if file.is_file() and folder.resolve() in file.resolve().parents:

            files.append(

                file.name
            )


    return {

        "success":
        True,

        "project":
        project,

        "version":
        version,

        "files":
        files
    }
