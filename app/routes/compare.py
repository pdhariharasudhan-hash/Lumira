from fastapi import APIRouter
import difflib
from app.services.projects.project_paths import resolve_project_path

router = APIRouter()


@router.get(
    "/compare/{project}/{old}/{new}"
)
def compare_versions(
    project: str,
    old: str,
    new: str
):

    old_file = resolve_project_path(project, old, "main.py")
    new_file = resolve_project_path(project, new, "main.py")

    if old_file and new_file and old_file.is_file() and new_file.is_file():
        if old_file.stat().st_size > 2_000_000 or new_file.stat().st_size > 2_000_000:
            return {"success": False, "message": "Project version file exceeds the comparison limit"}

        old_lines = old_file.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = new_file.read_text(encoding="utf-8").splitlines(keepends=True)
        diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=old, tofile=new))
        return {"success": True, "project": project, "comparison": diff}


    return {

        "success":
        False,

        "message":
        "versions not found"
    }
