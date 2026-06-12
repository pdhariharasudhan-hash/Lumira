from fastapi import APIRouter
from pathlib import Path
import difflib

router = APIRouter()


@router.get(
    "/compare/{project}/{old}/{new}"
)
def compare_versions(
    project: str,
    old: str,
    new: str
):

    generated = Path(
        "generated"
    )


    for date_folder in generated.iterdir():

        old_file = (
            date_folder
            / project
            / old
            / "main.py"
        )

        new_file = (
            date_folder
            / project
            / new
            / "main.py"
        )


        if (
            old_file.exists()
            and
            new_file.exists()
        ):

            with open(
                old_file,
                "r",
                encoding="utf-8"
            ) as f:

                old_lines = (
                    f.readlines()
                )


            with open(
                new_file,
                "r",
                encoding="utf-8"
            ) as f:

                new_lines = (
                    f.readlines()
                )


            diff = list(

                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=old,
                    tofile=new
                )
            )


            return {

                "success":
                True,

                "project":
                project,

                "comparison":
                diff
            }


    return {

        "success":
        False,

        "message":
        "versions not found"
    }