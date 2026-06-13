from app.services.projects.project_discovery_service import (
    ProjectDiscoveryService
)

from app.services.workspace.workspace_service import (
    WorkspaceService
)


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
        