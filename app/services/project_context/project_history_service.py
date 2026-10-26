from pathlib import Path
from datetime import datetime
import json


class ProjectHistoryService:

    def __init__(
        self
    ):

        self.history_file = Path(
            "memory/project_history.json"
        )

        self.history_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.history_file.exists():

            self._write(
                {}
            )

    def _read(
        self
    ):

        content = (
            self.history_file
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

        self.history_file.write_text(

            json.dumps(
                data,
                indent=2
            ),

            encoding="utf-8"
        )

    def log_event(
        self,
        project_name: str,
        event_type: str,
        details: dict
    ):

        data = (
            self._read()
        )

        data.setdefault(
            project_name,
            []
        )

        data[
            project_name
        ].append({

            "timestamp":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "event":
            event_type,

            "details":
            details
        })

        self._write(
            data
        )

        return {

            "success":
            True,

            "project":
            project_name,

            "event":
            event_type
        }

    def get_history(
        self,
        project_name: str
    ):

        data = (
            self._read()
        )

        return {

            "success":
            True,

            "project":
            project_name,

            "history":
            data.get(
                project_name,
                []
            )
        }

    def get_latest_events(
        self,
        project_name: str,
        limit: int = 10
    ):

        history = (

            self.get_history(
                project_name
            )[
                "history"
            ]
        )

        return {

            "success":
            True,

            "project":
            project_name,

            "events":
            history[-limit:]
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

    def clear_history(
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

        data[
            project_name
        ] = []

        self._write(
            data
        )

        return {

            "success":
            True,

            "project":
            project_name
        }