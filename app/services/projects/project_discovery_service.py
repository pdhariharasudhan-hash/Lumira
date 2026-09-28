from pathlib import Path
from typing import Dict, List, Optional
import json
from app.services.projects.project_paths import resolve_project_path


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

            safe_project = resolve_project_path(project_folder.name)
            if safe_project is None or safe_project != project_folder.resolve() or not project_folder.is_dir():

                continue

            versions = []

            version_folders = []
            for version_folder in project_folder.iterdir():
                safe_version = resolve_project_path(project_folder.name, version_folder.name)
                if safe_version is not None and safe_version == version_folder.resolve() and version_folder.is_dir():
                    version_folders.append(version_folder)
            version_folders.sort(key=lambda folder: int(folder.name[1:]))

            for version_folder in version_folders:

                metadata_file = (
                    version_folder
                    / "metadata.json"
                )

                if not metadata_file.is_file() or metadata_file.stat().st_size > 100_000:

                    continue
                if resolve_project_path(project_folder.name, version_folder.name, "metadata.json") != metadata_file.resolve():
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

                    if isinstance(metadata, dict):
                        versions.append(metadata)

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

        project_folder = resolve_project_path(project_name)

        if project_folder is None or not project_folder.is_dir():

            return []

        versions = []

        version_folders = []
        for version_folder in project_folder.iterdir():
            safe_version = resolve_project_path(project_name, version_folder.name)
            if safe_version is not None and safe_version == version_folder.resolve() and version_folder.is_dir():
                version_folders.append(version_folder)
        version_folders.sort(key=lambda folder: int(folder.name[1:]))

        for version_folder in version_folders:

            metadata_file = (
                version_folder
                / "metadata.json"
            )

            if not metadata_file.is_file() or metadata_file.stat().st_size > 100_000:

                continue
            if resolve_project_path(project_name, version_folder.name, "metadata.json") != metadata_file.resolve():
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

                if isinstance(metadata, dict):
                    versions.append(metadata)

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
