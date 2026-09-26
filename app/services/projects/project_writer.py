from typing import Dict
from pathlib import Path
import re
import json
from datetime import datetime

from app.services.project_context.project_context_service import (
    ProjectContextService
)

from app.services.project_context.project_history_service import (
    ProjectHistoryService
)


class ProjectWriter:

    def save(
        self,
        project_name: str,
        files: Dict[str, str],
        metadata: Dict
    ):

        project_name = str(project_name).strip()
        if not project_name or "/" in project_name or "\\" in project_name or project_name in {".", ".."}:
            raise ValueError("project_name must be a single safe path component")

        project_name = re.sub(r"[^A-Za-z0-9_-]+", "_", project_name).strip("_-")
        if not project_name:
            raise ValueError("project_name must contain letters or digits")

        generated_root = Path("generated").resolve()

        base_folder = (
            generated_root / project_name
        )

        if generated_root not in base_folder.resolve().parents:
            raise ValueError("project path escapes the generated directory")

        base_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        version = 1

        while (

            base_folder
            / f"v{version}"

        ).exists():

            version += 1

        folder = (

            base_folder
            / f"v{version}"
        )

        folder.mkdir(
            parents=True,
            exist_ok=True
        )

        for (
            filename,
            content
        ) in files.items():

            if (
                not isinstance(filename, str)
                or not filename
                or Path(filename).is_absolute()
                or "/" in filename
                or "\\" in filename
                or filename in {".", ".."}
            ):
                raise ValueError("generated filenames must be safe path components")

            file_path = (

                folder
                / filename
            )

            with open(
                file_path,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    content
                )

        metadata[
            "created"
        ] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        metadata[
            "version"
        ] = f"v{version}"

        project_version = (
            f"v{version}"
        )

        metadata[
            "status"
        ] = "generated"

        metadata_path = (
            folder
            / "metadata.json"
        )

        with open(
            metadata_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                metadata,
                f,
                indent=4
            )

        ProjectContextService().update_project(

            project_name=
            project_name,

            updates={

                "latest_version":
                project_version
            }
        )

        ProjectHistoryService().log_event(

            project_name,

            "version_created",

            {
                "version":
                project_version
            }
        )

        return str(
            folder
        )