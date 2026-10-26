from pathlib import Path
from datetime import datetime
import json
import uuid

from app.services.history.event_logger_service import (
    EventLoggerService
)


class ExecutionSessionService:

    def __init__(self):

        self.session_file = Path(
            "memory/execution_sessions.json"
        )

        self.session_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.session_file.exists():

            self._write(
                []
            )

    def _read(
        self
    ):

        content = (
            self.session_file
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        if not content:

            return []

        return json.loads(
            content
        )

    def _write(
        self,
        data
    ):

        self.session_file.write_text(
            json.dumps(
                data,
                indent=2
            ),
            encoding="utf-8"
        )

    def create_session(
        self,
        goal: str,
        builder: dict,
        execution: dict,
        code: dict
    ):

        sessions = (
            self._read()
        )

        session = {

            "session_id":
            str(
                uuid.uuid4()
            ),

            "goal":
            goal,

            "builder":
            builder,

            "execution":
            execution,

            "code":
            code,

            "status":
            "completed",

            "timestamp":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }

        sessions.append(
            session
        )

        self._write(
            sessions
        )

        EventLoggerService().log(
            event="execution_completed",
            source="executor",
            data={
                "goal":
                goal,

                "session_id":
                session[
                    "session_id"
                ]
            }
        )

        return session

    def latest(
        self
    ):

        sessions = (
            self._read()
        )

        if not sessions:

            return {

                "success":
                False,

                "message":
                "no sessions found"
            }

        return sessions[-1]

    def get_sessions(
        self
    ):

        return self._read()

    def get_session(
        self,
        session_id: str
    ):

        sessions = (
            self._read()
        )

        for session in sessions:

            if session[
                "session_id"
            ] == session_id:

                return session

        return {

            "success":
            False,

            "message":
            "session not found"
        }

    def delete_session(
        self,
        session_id: str
    ):

        sessions = (
            self._read()
        )

        filtered = []

        found = False

        for session in sessions:

            if session[
                "session_id"
            ] == session_id:

                found = True

                continue

            filtered.append(
                session
            )

        self._write(
            filtered
        )

        return {

            "success":
            found
        }

    def count(
        self
    ):

        sessions = (
            self._read()
        )

        return {

            "success":
            True,

            "count":
            len(
                sessions
            )
        }