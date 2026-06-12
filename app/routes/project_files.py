from fastapi import APIRouter
from pathlib import Path

router = APIRouter()


@router.get(
    "/projects/{project}/{version}/files"
)
def get_project_files(
    project: str,
    version: str
):

    folder = (

        Path(
            "generated"
        )

        / project

        / version
    )


    if not folder.exists():

        return {

            "success":
            False,

            "message":
            "Project version not found"
        }


    files = []


    for file in folder.iterdir():

        if file.is_file():

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