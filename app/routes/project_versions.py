from fastapi import APIRouter
from pathlib import Path

router = APIRouter()


@router.get(
    "/projects/{project}"
)
def get_versions(
    project: str
):

    project_path = (
        Path("generated")
        / project
    )


    if not project_path.exists():

        return {

            "success":
            False,

            "message":
            "Project not found"
        }


    versions = []


    for version in project_path.iterdir():

        if version.is_dir():

            versions.append(
                version.name
            )


    versions.sort(
        key=lambda x:
        int(
            x.replace(
                "v",
                ""
            )
        )
    )


    return {

        "success":
        True,

        "project":
        project,

        "versions":
        versions
    }