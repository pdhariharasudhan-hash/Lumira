from pathlib import Path
import json
from datetime import datetime

from app.services.project_context.project_history_service import (
    ProjectHistoryService
)


class ProjectContextService:

    def __init__(
        self
    ):

        self.registry_file = Path(
            "memory/project_registry.json"
        )

        self.registry_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.registry_file.exists():

            self._write(
                {}
            )

    def _read(
        self
    ):

        content = (
            self.registry_file
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        if not content:

            return {}

        return json.loads(
            content
        )

    def _write(
        self,
        data
    ):

        self.registry_file.write_text(
            json.dumps(
                data,
                indent=2
            ),
            encoding="utf-8"
        )

    def create_project(
        self,
        project_name: str,
        goal: str,
        workspace: str = "default"
    ):

        data = (
            self._read()
        )

        if project_name in data:

            return {

                "success":
                False,

                "message":
                "project exists"
            }

        timestamp = (
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        data[
            project_name
        ] = {

            "goal":
            goal,

            "workspace":
            workspace,

            "path":
            f"generated/{project_name}",

            "latest_version":
            "v1",

            "created":
            timestamp,

            "updated":
            timestamp,

            "status":
            "active",

            "features":
            []
        }

        self._write(
            data
        )

        ProjectHistoryService().log_event(

            project_name,

            "project_created",

            {
                "goal":
                goal
            }
        )

        return {

            "success":
            True,

            "project":
            project_name
        }

    def get_project(
        self,
        project_name: str
    ):

        data = (
            self._read()
        )

        if project_name not in data:

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
            data[
                project_name
            ]
        }

    def update_project(
        self,
        project_name: str,
        updates: dict
    ):

        data = (
            self._read()
        )

        if project_name not in data:

            return {

                "success":
                False,

                "message":
                "project not found"
            }

        updates[
            "updated"
        ] = (

            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        data[
            project_name
        ].update(
            updates
        )

        self._write(
            data
        )

        return {

            "success":
            True
        }

    def delete_project(
        self,
        project_name: str
    ):

        data = (
            self._read()
        )

        if project_name not in data:

            return {

                "success":
                False,

                "message":
                "project not found"
            }

        del data[
            project_name
        ]

        self._write(
            data
        )

        return {

            "success":
            True
        }

    def list_projects(
        self
    ):

        data = (
            self._read()
        )

        return {

            "success":
            True,

            "count":
            len(
                data
            ),

            "projects":
            list(
                data.keys()
            )
        }