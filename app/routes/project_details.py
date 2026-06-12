from fastapi import APIRouter
from pathlib import Path
import json

router = APIRouter()


@router.get(
    "/projects/{project}/{version}"
)
def get_project(
    project: str,
    version: str
):

    project_folder = (

        Path(
            "generated"
        )

        / project

        / version
    )


    if not project_folder.exists():

        return {

            "success":
            False,

            "message":
            "project not found"
        }


    result = {}


    metadata_file = (

        project_folder
        / "metadata.json"
    )


    if metadata_file.exists():

        with open(
            metadata_file,
            "r",
            encoding="utf-8"
        ) as f:

            result[
                "metadata"
            ] = json.load(
                f
            )


    files = {}


    for file in project_folder.iterdir():

        if (
            file.name
            ==
            "metadata.json"
        ):

            continue


        with open(
            file,
            "r",
            encoding="utf-8"
        ) as f:

            files[
                file.name
            ] = f.read()


    result[
        "files"
    ] = files


    return {

        "success":
        True,

        "project":
        project,

        "version":
        version,

        "data":
        result
    }