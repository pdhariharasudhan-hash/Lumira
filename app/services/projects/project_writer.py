from typing import Dict
from pathlib import Path
import json
from datetime import datetime

from app.services.project_context.project_context_service import (
    ProjectContextService
)


class ProjectWriter:

    def save(
        self,
        project_name: str,
        files: Dict[str, str],
        metadata: Dict
    ):

        base_folder = (

            Path(
                "generated"
            )

            / project_name
        )

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

        return str(
            folder
        )