from pathlib import Path
import json

from app.services.execution.execution_context_service import (
    ExecutionContextService
)


class SnapshotService:

    def __init__(self):

        self.snapshot_file = Path(
            "memory/snapshots.json"
        )

        self.snapshot_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.snapshot_file.exists():

            self._write(
                {}
            )

        self.context = (
            ExecutionContextService()
        )

    def _read(self):

        content = (
            self.snapshot_file
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

        self.snapshot_file.write_text(
            json.dumps(
                data,
                indent=2
            ),
            encoding="utf-8"
        )

    def save_snapshot(
        self,
        name: str
    ):

        snapshots = (
            self._read()
        )

        snapshots[
            name
        ] = (
            self.context
            .get_context()
        )

        self._write(
            snapshots
        )

        return {

            "success":
            True,

            "snapshot":
            name
        }

    def restore_snapshot(
        self,
        name: str
    ):

        snapshots = (
            self._read()
        )

        if name not in snapshots:

            return {

                "success":
                False,

                "message":
                "snapshot not found"
            }

        self.context._write(
            snapshots[
                name
            ]
        )

        return {

            "success":
            True,

            "snapshot":
            name
        }

    def delete_snapshot(
        self,
        name: str
    ):

        snapshots = (
            self._read()
        )

        if name not in snapshots:

            return {

                "success":
                False,

                "message":
                "snapshot not found"
            }

        del snapshots[
            name
        ]

        self._write(
            snapshots
        )

        return {

            "success":
            True
        }

    def list_snapshots(
        self
    ):

        snapshots = (
            self._read()
        )

        return {

            "count":
            len(
                snapshots
            ),

            "snapshots":
            list(
                snapshots.keys()
            )
        }