from pathlib import Path
from datetime import datetime, timezone
from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.sessions.session_manager_service import redact_sensitive_text, redact_sensitive_value

MAX_HISTORY_RECORDS = 1000


class PipelineHistoryService:

    def __init__(self):
        self.history_file = Path(
            "memory/pipeline_history.json"
        )

        self.history_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.store = AtomicJsonStore(self.history_file)
        if not self.history_file.exists():
            self.store.write([])

    def _read(self):
        records = self.store.read([])
        if not isinstance(records, list):
            raise PersistenceIntegrityError("Pipeline history must be a list")
        if any(not isinstance(record, dict) for record in records):
            raise PersistenceIntegrityError("Pipeline history contains an invalid record")
        for record in records[-MAX_HISTORY_RECORDS:]:
            for field_name, limit in (("execution_id", 128), ("request_id", 128), ("session_id", 128), ("project_id", 128), ("user_input", 10000), ("error", 4000), ("timestamp", 40)):
                value = record.get(field_name)
                if value is not None and (not isinstance(value, str) or len(value) > limit):
                    raise PersistenceIntegrityError(f"Pipeline history field {field_name} is invalid")
            if "success" in record and not isinstance(record["success"], bool):
                raise PersistenceIntegrityError("Pipeline history success state is invalid")
            if "stage_count" in record and (not isinstance(record["stage_count"], int) or isinstance(record["stage_count"], bool) or not 0 <= record["stage_count"] <= 500):
                raise PersistenceIntegrityError("Pipeline history stage count is invalid")
            if "trace" in record and (not isinstance(record["trace"], list) or len(record["trace"]) > 500):
                raise PersistenceIntegrityError("Pipeline history trace is invalid")
        # Bound every reader, including older stores that predate write-time retention.
        return records[-MAX_HISTORY_RECORDS:]

    def _write(self, data):
        if not isinstance(data, list):
            raise PersistenceIntegrityError("Pipeline history must be a list")
        self.store.write(data[-MAX_HISTORY_RECORDS:])

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
        # A pipeline can run without an active project. Keep that state explicit
        # as an empty project_id instead of failing the entire user request.
        for field_name, field_value in (("execution_id", execution_id), ("request_id", request_id), ("session_id", session_id)):
            if not isinstance(field_value, str) or not field_value.strip() or len(field_value) > 128:
                raise ValueError(f"{field_name} must contain 1 to 128 characters")
        if not isinstance(project_id, str) or len(project_id) > 128:
            raise ValueError("project_id must be a string of at most 128 characters")
        if not isinstance(user_input, str) or len(user_input) > 100_000:
            raise ValueError("user_input must be a string of at most 100000 characters")
        if not isinstance(success, bool):
            raise ValueError("success must be a boolean")
        if not isinstance(trace, list) or len(trace) > 500:
            raise ValueError("trace must be a list of at most 500 stages")
        record = {
            "execution_id": execution_id,
            "request_id": request_id,
            "session_id": session_id,
            "project_id": project_id,
            "user_input": redact_sensitive_text(str(user_input))[:10000],
            "success": success,
            "error": redact_sensitive_text(str(error))[:4000] if error is not None else None,
            "trace": redact_sensitive_value(trace),
            "stage_count": len(trace),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        def append(history):
            if not isinstance(history, list):
                raise PersistenceIntegrityError("Pipeline history must be a list")
            history.append(record)
            del history[:-MAX_HISTORY_RECORDS]

        self.store.update(append, [])

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

        query = query.strip().lower()[:4000]

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

