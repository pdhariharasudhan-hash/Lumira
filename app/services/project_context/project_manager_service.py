from app.services.project_context.project_context_service import (
    ProjectContextService
)

from app.services.project_context.project_history_service import (
    ProjectHistoryService
)

from app.services.project_context.project_health_service import (
    ProjectHealthService
)

from app.services.project_context.registry_migration_service import (
    RegistryMigrationService
)


class ProjectManagerService:

    def __init__(
        self
    ):

        self.context = (
            ProjectContextService()
        )

        self.history = (
            ProjectHistoryService()
        )

        self.health = (
            ProjectHealthService()
        )

        self.migration = (
            RegistryMigrationService()
        )

    def create_project(
        self,
        project_name: str,
        goal: str,
        workspace: str = "default"
    ):

        return (

            self.context
            .create_project(

                project_name=
                project_name,

                goal=
                goal,

                workspace=
                workspace
            )
        )

    def get_project(
        self,
        project_name: str
    ):

        return (

            self.context
            .get_project(
                project_name
            )
        )

    def update_project(
        self,
        project_name: str,
        updates: dict
    ):

        return (

            self.context
            .update_project(

                project_name,
                updates
            )
        )

    def delete_project(
        self,
        project_name: str
    ):

        return (

            self.context
            .delete_project(
                project_name
            )
        )

    def list_projects(
        self
    ):

        return (

            self.context
            .list_projects()
        )

    def get_history(
        self,
        project_name: str
    ):

        return (

            self.history
            .get_history(
                project_name
            )
        )

    def get_latest_events(
        self,
        project_name: str,
        limit: int = 10
    ):

        return (

            self.history
            .get_latest_events(

                project_name,

                limit
            )
        )

    def check_project_health(
        self,
        project_name: str
    ):

        return (

            self.health
            .check_project(
                project_name
            )
        )

    def check_all_projects_health(
        self
    ):

        return (

            self.health
            .check_all_projects()
        )

    def detect_orphans(
        self
    ):

        return (

            self.health
            .detect_orphans()
        )

    def detect_version_mismatches(
        self
    ):

        return (

            self.health
            .detect_version_mismatches()
        )

    def migrate_project(
        self,
        project_name: str
    ):

        return (

            self.migration
            .migrate_project(
                project_name
            )
        )

    def migrate_all_projects(
        self
    ):

        return (

            self.migration
            .migrate_all()
        )