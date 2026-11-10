from pathlib import Path
import json

from app.services.projects.project_discovery_service import (
    ProjectDiscoveryService
)

from app.services.workspace.workspace_service import (
    WorkspaceService
)

from app.services.projects.project_paths import resolve_project_path


class ProjectLifecycleService:

    def __init__(
        self
    ):

        self.discovery = (
            ProjectDiscoveryService()
        )

        self.workspace = (
            WorkspaceService()
        )

    def list_projects(
        self
    ):

        return {

            "success":
            True,

            "projects":
            self.discovery.get_projects()
        }

    def get_project(
        self,
        project_name: str
    ):

        project = (
            self.discovery.get_project(
                project_name
            )
        )

        if not project:

            return {

                "success":
                False,

                "message":
                "project not found"
            }

        return {

            "success":
            True,

            "project":
            project
        }

    def get_versions(
        self,
        project_name: str
    ):

        return {

            "success":
            True,

            "versions":
            self.discovery.get_versions(
                project_name
            )
        }

    def get_workspace_projects(
        self
    ):

        return (
            self.workspace
            .list_projects()
        )

    def get_project_version(
        self,
        project_name: str,
        version: str
    ):

        project_folder = resolve_project_path(project_name, version)

        if project_folder is None or not project_folder.is_dir():

            return {

                "success":
                False,

                "message":
                "project not found"
            }

        result = {}
        total_bytes = 0

        metadata_file = (

            project_folder
            / "metadata.json"
        )

        if metadata_file.is_file():
            if metadata_file.stat().st_size > 100_000:
                return {"success": False, "message": "Project metadata exceeds the read limit"}
            if project_folder.resolve() not in metadata_file.resolve().parents:
                return {"success": False, "message": "Project metadata is outside the version directory"}

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

            resolved_file = file.resolve()
            if project_folder.resolve() not in resolved_file.parents or not file.is_file():
                continue
            file_size = file.stat().st_size
            total_bytes += file_size
            if file_size > 2_000_000 or total_bytes > 10_000_000:
                return {"success": False, "message": "Project version exceeds the read limit"}

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
            project_name,

            "version":
            version,

            "data":
            result
        }

    def continue_latest_project(
        self,
        project_name: str,
        instruction: str,
    ):
        project = self.discovery.get_project(project_name)
        if not isinstance(project, dict):
            return {
                "success": False,
                "status": "reject",
                "code": "project_not_found",
                "error": "Project not found.",
            }
        latest = project.get("latest")
        version = latest.get("version") if isinstance(latest, dict) else None
        if not isinstance(version, str):
            return {
                "success": False,
                "status": "reject",
                "code": "latest_project_version_missing",
                "error": "The project has no valid saved version to continue.",
            }
        return self.continue_project_version(project_name, version, instruction)

    def continue_project_version(
        self,
        project_name: str,
        version: str,
        instruction: str,
    ):
        existing = self.get_project_version(project_name, version)
        if not existing.get("success"):
            return {
                "success": False,
                "status": "reject",
                "code": "project_version_not_found",
                "error": existing.get("message", "Project version not found."),
            }

        data = existing.get("data")
        if not isinstance(data, dict):
            return {
                "success": False,
                "status": "reject",
                "code": "project_version_invalid",
                "error": "Project version data is invalid.",
            }

        from app.services.projects.project_continuation_service import ProjectContinuationService

        return ProjectContinuationService().continue_version(
            project_name=project_name,
            version=version,
            metadata=data.get("metadata"),
            files=data.get("files"),
            instruction=instruction,
        )

    def continue_project(self, metadata: dict, instruction: str, files: dict | None = None):
        if not isinstance(metadata, dict) or not isinstance(files, dict):
            return {
                "success": False,
                "status": "reject",
                "code": "source_files_required",
                "error": "Project continuation requires the saved source files, not metadata alone.",
            }
        project_name = metadata.get("project")
        version = metadata.get("version")
        if not isinstance(project_name, str) or not isinstance(version, str):
            return {
                "success": False,
                "status": "reject",
                "code": "project_version_required",
                "error": "Project metadata must identify its project and saved version.",
            }
        from app.services.projects.project_continuation_service import ProjectContinuationService
        return ProjectContinuationService().continue_version(
            project_name=project_name,
            version=version,
            metadata=metadata,
            files=files,
            instruction=instruction,
        )