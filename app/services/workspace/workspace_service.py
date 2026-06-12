from pathlib import Path
import json

from app.services.history.event_logger_service import (
    EventLoggerService
)


class WorkspaceService:

    def __init__(self):

        self.workspace_file = Path(
            "memory/workspaces.json"
        )

        self.workspace_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.workspace_file.exists():

            self._write(
                {
                    "active_workspace": "default",
                    "workspaces": {
                        "default": {
                            "projects": [],
                            "collections": [],
                            "snapshots": []
                        }
                    }
                }
            )

    def _read(
        self
    ):

        content = (
            self.workspace_file
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        if not content:

            return {
                "active_workspace":
                "default",

                "workspaces":
                {}
            }

        return json.loads(
            content
        )

    def _write(
        self,
        data
    ):

        self.workspace_file.write_text(
            json.dumps(
                data,
                indent=2
            ),
            encoding="utf-8"
        )

    def create_workspace(
        self,
        name: str
    ):

        data = (
            self._read()
        )

        if name in data[
            "workspaces"
        ]:

            return {

                "success":
                False,

                "message":
                "workspace exists"
            }

        data[
            "workspaces"
        ][
            name
        ] = {

            "projects":
            [],

            "collections":
            [],

            "snapshots":
            []
        }

        self._write(
            data
        )

        EventLoggerService().log(
            event="workspace_created",
            source="workspace",
            data={
                "workspace":
                name
            }
        )

        return {

            "success":
            True,

            "workspace":
            name
        }

    def switch_workspace(
        self,
        name: str
    ):

        data = (
            self._read()
        )

        if name not in data[
            "workspaces"
        ]:

            return {

                "success":
                False,

                "message":
                "workspace not found"
            }

        data[
            "active_workspace"
        ] = name

        self._write(
            data
        )

        EventLoggerService().log(
            event="workspace_switched",
            source="workspace",
            data={
                "workspace":
                name
            }
        )

        return {

            "success":
            True,

            "active_workspace":
            name
        }

    def get_active_workspace(
        self
    ):

        data = (
            self._read()
        )

        return {

            "success":
            True,

            "active_workspace":
            data[
                "active_workspace"
            ]
        }

    def list_workspaces(
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
                data[
                    "workspaces"
                ]
            ),

            "workspaces":
            list(
                data[
                    "workspaces"
                ].keys()
            )
        }

    def delete_workspace(
        self,
        name: str
    ):

        data = (
            self._read()
        )

        if name == "default":

            return {

                "success":
                False,

                "message":
                "cannot delete default workspace"
            }

        if name not in data[
            "workspaces"
        ]:

            return {

                "success":
                False,

                "message":
                "workspace not found"
            }

        del data[
            "workspaces"
        ][
            name
        ]

        if data[
            "active_workspace"
        ] == name:

            data[
                "active_workspace"
            ] = "default"

        self._write(
            data
        )

        EventLoggerService().log(
            event="workspace_deleted",
            source="workspace",
            data={
                "workspace":
                name
            }
        )

        return {

            "success":
            True
        }

    def get_workspace(
        self,
        name: str
    ):

        data = (
            self._read()
        )

        if name not in data[
            "workspaces"
        ]:

            return {

                "success":
                False,

                "message":
                "workspace not found"
            }

        return {

            "success":
            True,

            "workspace":
            data[
                "workspaces"
            ][
                name
            ]
        }