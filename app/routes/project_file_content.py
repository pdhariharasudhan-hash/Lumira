from fastapi import APIRouter
from pathlib import Path
from fastapi import HTTPException
from app.services.projects.project_paths import resolve_project_path


router = APIRouter()


@router.get(
    "/projects/{project}/{version}/{file_name}"
)
def get_file_content(
    project: str,
    version: str,
    file_name: str
):

    file_path = resolve_project_path(project, version, file_name)

    if file_path is None or not file_path.is_file():

        return {

            "success":
            False,

            "message":
            "File not found"
        }


    if file_path.stat().st_size > 2_000_000:
        raise HTTPException(status_code=413, detail="Project file exceeds the read limit")

    try:

        content = (

            file_path
            .read_text(
                encoding="utf-8"
            )
        )


        return {

            "success":
            True,

            "project":
            project,

            "version":
            version,

            "file":
            file_name,

            "content":
            content
        }

    except Exception as e:

        return {

            "success":
            False,

            "message":
            str(
                e
            )
        }
