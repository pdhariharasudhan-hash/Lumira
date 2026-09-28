import re
from pathlib import Path


PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
PROJECT_VERSION_PATTERN = re.compile(r"^v[1-9][0-9]{0,8}$")
PROJECT_FILE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")


def resolve_project_path(
    project: str,
    version: str | None = None,
    file_name: str | None = None,
    root: str | Path = "generated",
) -> Path | None:
    if not isinstance(project, str) or not PROJECT_NAME_PATTERN.fullmatch(project):
        return None
    parts = [project]
    if version is not None:
        if not isinstance(version, str) or not PROJECT_VERSION_PATTERN.fullmatch(version):
            return None
        parts.append(version)
    if file_name is not None:
        if (
            not isinstance(file_name, str)
            or not PROJECT_FILE_PATTERN.fullmatch(file_name)
            or file_name in {".", ".."}
        ):
            return None
        parts.append(file_name)

    base = Path(root).resolve()
    raw_candidate = base.joinpath(*parts)
    cursor = base
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            return None
    candidate = raw_candidate.resolve()
    if candidate == base or base not in candidate.parents:
        return None
    if file_name is not None:
        expected_parent = base.joinpath(*parts[:-1]).resolve()
        if candidate.parent != expected_parent:
            return None
    return candidate
