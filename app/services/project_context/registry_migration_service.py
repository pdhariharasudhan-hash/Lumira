from pathlib import Path

from app.services.project_context.project_context_service import (
    ProjectContextService
)


class RegistryMigrationService:

    def __init__(
        self
    ):

        self.context = (
            ProjectContextService()
        )

        self.generated_path = Path(
            "generated"
        )

    def rebuild_latest_version(
        self,
        project_name: str
    ):

        project_folder = (
            self.generated_path
            / project_name
        )

        if not project_folder.exists():

            return None

        versions = []

        for folder in project_folder.iterdir():

            if (
                folder.is_dir()
                and folder.name.startswith(
                    "v"
                )
            ):

                try:

                    versions.append(

                        int(
                            folder.name.replace(
                                "v",
                                ""
                            )
                        )
                    )

                except ValueError:

                    pass

        if not versions:

            return None

        return (
            f"v{max(versions)}"
        )

    def rebuild_path(
        self,
        project_name: str
    ):

        project_folder = (
            self.generated_path
            / project_name
        )

        if not project_folder.exists():

            return None

        return str(
            project_folder
        )

    def migrate_project(
        self,
        project_name: str
    ):

        project_result = (
            self.context.get_project(
                project_name
            )
        )

        if not project_result[
            "success"
        ]:

            return {

                "success":
                False,

                "project":
                project_name
            }

        project = (
            project_result[
                "project"
            ]
        )

        updates = {}

        if "workspace" not in project:

            updates[
                "workspace"
            ] = "default"

        if "path" not in project:

            updates[
                "path"
            ] = (
                self.rebuild_path(
                    project_name
                )
            )

        if (
            "latest_version"
            not in project
            or project[
                "latest_version"
            ] is None
        ):

            updates[
                "latest_version"
            ] = (
                self.rebuild_latest_version(
                    project_name
                )
            )

        if "created" not in project:

            updates[
                "created"
            ] = ""

        if "updated" not in project:

            updates[
                "updated"
            ] = ""

        if "status" not in project:

            updates[
                "status"
            ] = "active"

        if "features" not in project:

            updates[
                "features"
            ] = []

        if updates:

            self.context.update_project(

                project_name=
                project_name,

                updates=
                updates
            )

        return {

            "success":
            True,

            "project":
            project_name,

            "updates":
            updates
        }

    def migrate_all(
        self
    ):

        projects = (
            self.context
            .list_projects()
        )

        migrated = 0

        results = []

        for project_name in projects[
            "projects"
        ]:

            result = (
                self.migrate_project(
                    project_name
                )
            )

            results.append(
                result
            )

            if result[
                "success"
            ]:

                migrated += 1

        return {

            "success":
            True,

            "migrated":
            migrated,

            "results":
            results
        }