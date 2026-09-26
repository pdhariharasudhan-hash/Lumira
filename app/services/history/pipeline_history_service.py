from pathlib import Path
from datetime import datetime
import json


class PipelineHistoryService:

    def __init__(self):
        self.history_file = Path(
            "memory/pipeline_history.json"
        )

        self.history_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.history_file.exists():
            self._write([])

    def _read(self):
        content = (
            self.history_file
            .read_text(encoding="utf-8")
            .strip()
        )

        if not content:
            return []

        return json.loads(content)

    def _write(self, data):
        self.history_file.write_text(
            json.dumps(
                data,
                indent=2
            ),
            encoding="utf-8"
        )

    def record(
        self,
        execution_id: str,
        request_id: str,
        session_id: str,
        project_id: str,
        user_input: str,
        success: bool,
        trace: list,
        error=None,
    ):
        history = self._read()

        record = {
            "execution_id": execution_id,
            "request_id": request_id,
            "session_id": session_id,
            "project_id": project_id,
            "user_input": user_input,
            "success": success,
            "error": error,
            "trace": trace,
            "stage_count": len(trace),
            "timestamp": datetime.utcnow().isoformat(),
        }

        history.append(record)
        self._write(history)

        return record

    def get_history(self):
        return self._read()

    def get_by_execution_id(self, execution_id):
        """Return the pipeline history record for an execution ID."""
        if not isinstance(execution_id, str) or not execution_id.strip():
            return None

        target = execution_id.strip()

        for record in self._read():
            if record.get("execution_id") == target:
                return record

        return None

    def get_by_request_id(self, request_id):
        """Return the pipeline history record for a request ID."""
        if not isinstance(request_id, str) or not request_id.strip():
            return None

        target = request_id.strip()

        for record in self._read():
            if record.get("request_id") == target:
                return record

        return None

    def get_by_session_id(self, session_id):
        """Return all pipeline history records for a session."""
        if not isinstance(session_id, str) or not session_id.strip():
            return []

        target = session_id.strip()

        return [
            record
            for record in self._read()
            if record.get("session_id") == target
        ]

    def get_by_project_id(self, project_id):
        """Return all pipeline history records for a project."""
        if not isinstance(project_id, str) or not project_id.strip():
            return []

        target = project_id.strip()

        return [
            record
            for record in self._read()
            if record.get("project_id") == target
        ]

    def search(self, query):
        """Search pipeline history using deterministic record text matching."""
        if not isinstance(query, str):
            return []

        query = query.strip().lower()

        if not query:
            return []

        results = []

        for record in self._read():
            searchable = " ".join(
                [
                    str(record.get("execution_id", "")),
                    str(record.get("request_id", "")),
                    str(record.get("session_id", "")),
                    str(record.get("project_id", "")),
                    str(record.get("user_input", "")),
                    str(record.get("success", "")),
                    str(record.get("error", "")),
                ]
            ).lower()

            if query in searchable:
                results.append(record)

        return results

    def latest(self):
        history = self._read()

        if not history:
            return None

        return history[-1]

    def count(self):
        return len(self._read())

    def query(
        self,
        session_id=None,
        project_id=None,
        success=None,
        limit=None,
        newest_first=True,
    ):
        """Return filtered and deterministically ordered pipeline history."""

        records = self._read()

        if session_id is not None:
            if not isinstance(session_id, str):
                return []

            session_id = session_id.strip()

            if not session_id:
                return []

            records = [
                record
                for record in records
                if record.get("session_id") == session_id
            ]

        if project_id is not None:
            if not isinstance(project_id, str):
                return []

            project_id = project_id.strip()

            if not project_id:
                return []

            records = [
                record
                for record in records
                if record.get("project_id") == project_id
            ]

        if success is not None:
            if not isinstance(success, bool):
                return []

            records = [
                record
                for record in records
                if record.get("success") is success
            ]

        def sort_key(record):
            return (
                str(record.get("timestamp", "")),
                str(record.get("execution_id", "")),
            )

        records = sorted(
            records,
            key=sort_key,
            reverse=bool(newest_first),
        )

        if limit is not None:
            if isinstance(limit, bool):
                return []

            if not isinstance(limit, int):
                return []

            if limit < 0:
                return []

            records = records[:limit]

        return records

    def stats(self):
        """Return deterministic aggregate statistics for pipeline history."""

        records = self._read()

        total = len(records)
        successful = sum(
            1
            for record in records
            if record.get("success") is True
        )
        failed = sum(
            1
            for record in records
            if record.get("success") is False
        )

        sessions = {
            record.get("session_id")
            for record in records
            if record.get("session_id")
        }

        projects = {
            record.get("project_id")
            for record in records
            if record.get("project_id")
        }

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "sessions": len(sessions),
            "projects": len(projects),
        }

    def clear(self):
        self._write([])

        return {
            "success": True
        }

