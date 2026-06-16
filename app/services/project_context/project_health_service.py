from pathlib import Path

from app.services.project_context.project_context_service import (
    ProjectContextService
)

from app.services.project_context.project_history_service import (
    ProjectHistoryService
)


class ProjectHealthService:

    def __init__(
        self
    ):

        self.context = (
            ProjectContextService()
        )

        self.generated_path = Path(
            "generated"
        )

    def check_project(
        self,
        project_name: str
    ):

        issues = []

        project_result = (
            self.context.get_project(
                project_name
            )
        )

        if not project_result[
            "success"
        ]:

            return {

                "project":
                project_name,

                "health":
                "error",

                "issues": [
                    "project not found"
                ]
            }

        project = (
            project_result[
                "project"
            ]
        )

        path = project.get(
            "path"
        )

        latest_version = project.get(
            "latest_version"
        )

        if not path:

            issues.append(
                "missing generated folder"
            )

        else:

            project_folder = Path(
                path
            )

            if not project_folder.exists():

                issues.append(
                    "generated folder does not exist"
                )

        if not latest_version:

            issues.append(
                "latest_version unknown"
            )

        else:

            version_folder = (

                self.generated_path
                / project_name
                / latest_version
            )

            if not version_folder.exists():

                issues.append(
                    "latest version folder missing"
                )

            metadata_file = (
                version_folder
                / "metadata.json"
            )

            if not metadata_file.exists():

                issues.append(
                    "metadata.json missing"
                )

        if issues:

            ProjectHistoryService().log_event(

                project_name,

                "health_warning",

                {
                    "issues":
                    issues
                }
            )

        return {

            "project":
            project_name,

            "health":
            (
                "healthy"
                if not issues
                else "warning"
            ),

            "issues":
            issues
        }

    def check_all_projects(
        self
    ):

        projects = (
            self.context
            .list_projects()
        )

        results = []

        healthy = 0

        warnings = 0

        for project_name in projects[
            "projects"
        ]:

            result = (
                self.check_project(
                    project_name
                )
            )

            results.append(
                result
            )

            if result[
                "health"
            ] == "healthy":

                healthy += 1

            else:

                warnings += 1

        return {

            "success":
            True,

            "healthy":
            healthy,

            "warnings":
            warnings,

            "results":
            results
        }

    def detect_orphans(
        self
    ):

        projects = (
            self.context
            .list_projects()
        )

        orphans = []

        for project_name in projects[
            "projects"
        ]:

            project = (

                self.context
                .get_project(
                    project_name
                )
            )[
                "project"
            ]

            if not project.get(
                "path"
            ):

                orphans.append(
                    project_name
                )

        return {

            "success":
            True,

            "count":
            len(
                orphans
            ),

            "orphans":
            orphans
        }

    def detect_version_mismatches(
        self
    ):

        mismatches = []

        projects = (
            self.context
            .list_projects()
        )

        for project_name in projects[
            "projects"
        ]:

            project = (

                self.context
                .get_project(
                    project_name
                )
            )[
                "project"
            ]

            latest_version = (
                project.get(
                    "latest_version"
                )
            )

            if not latest_version:

                mismatches.append({

                    "project":
                    project_name,

                    "issue":
                    "latest_version unknown"
                })

                continue

            version_folder = (

                self.generated_path
                / project_name
                / latest_version
            )

            if not version_folder.exists():

                mismatches.append({

                    "project":
                    project_name,

                    "issue":
                    "version folder missing"
                })

        return {

            "success":
            True,

            "count":
            len(
                mismatches
            ),

            "mismatches":
            mismatches
        }