from pathlib import Path
from typing import Dict, List, Optional
import json


class ProjectDiscoveryService:

    def __init__(self):

        self.generated_path = Path(
            "generated"
        )

    def get_projects(
        self
    ) -> List[Dict]:

        projects = []

        if not self.generated_path.exists():

            return projects

        for project_folder in self.generated_path.iterdir():

            if not project_folder.is_dir():

                continue

            versions = []

            for version_folder in sorted(
                project_folder.iterdir()
            ):

                if not version_folder.is_dir():

                    continue

                metadata_file = (
                    version_folder
                    / "metadata.json"
                )

                if not metadata_file.exists():

                    continue

                try:

                    with open(
                        metadata_file,
                        "r",
                        encoding="utf-8"
                    ) as f:

                        metadata = json.load(
                            f
                        )

                    versions.append(
                        metadata
                    )

                except Exception:

                    continue

            projects.append({

                "project":
                project_folder.name,

                "versions":
                len(
                    versions
                ),

                "latest":
                versions[-1]
                if versions
                else None
            })

        return projects

    def get_project(
        self,
        project_name: str
    ) -> Optional[Dict]:

        projects = self.get_projects()

        for project in projects:

            if project[
                "project"
            ] == project_name:

                return project

        return None

    def get_versions(
        self,
        project_name: str
    ) -> List[Dict]:

        project_folder = (
            self.generated_path
            / project_name
        )

        if not project_folder.exists():

            return []

        versions = []

        for version_folder in sorted(
            project_folder.iterdir()
        ):

            if not version_folder.is_dir():

                continue

            metadata_file = (
                version_folder
                / "metadata.json"
            )

            if not metadata_file.exists():

                continue

            try:

                with open(
                    metadata_file,
                    "r",
                    encoding="utf-8"
                ) as f:

                    metadata = json.load(
                        f
                    )

                versions.append(
                    metadata
                )

            except Exception:

                continue

        return versions

    def get_metadata(
        self,
        project_name: str
    ):

        project = self.get_project(
            project_name
        )

        if not project:

            return None

        return project.get(
            "latest"
        )