from fastapi import APIRouter
from pathlib import Path


router = APIRouter()


@router.get(
    "/projects/{project}/{version}/{file_name}"
)
def get_file_content(
    project: str,
    version: str,
    file_name: str
):

    file_path = (

        Path(
            "generated"
        )

        / project

        / version

        / file_name
    )


    if not file_path.exists():

        return {

            "success":
            False,

            "message":
            "File not found"
        }


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