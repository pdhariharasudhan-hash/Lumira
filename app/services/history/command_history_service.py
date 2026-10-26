from pathlib import Path
from datetime import datetime, timezone
from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.sessions.session_manager_service import redact_sensitive_text, redact_sensitive_value

MAX_HISTORY_RECORDS = 1000


class CommandHistoryService:

    def __init__(self):
        self.history_file = Path(
            "memory/command_history.json"
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
            raise PersistenceIntegrityError("Command history must be a list")
        return records

    def _write(self, data):
        if not isinstance(data, list):
            raise PersistenceIntegrityError("Command history must be a list")
        self.store.write(data[-MAX_HISTORY_RECORDS:])

    def record(
        self,
        request_id: str,
        execution_id: str,
        session_id: str,
        project_id: str,
        message: str,
        environment: str,
        workspace: str,
        metadata: dict,
    ):
        record = {
            "request_id": request_id,
            "execution_id": execution_id,
            "session_id": session_id,
            "project_id": project_id,
            "message": redact_sensitive_text(str(message))[:10000],
            "environment": environment,
            "workspace": workspace,
            "metadata": redact_sensitive_value(metadata or {}),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }

        def append(history):
            if not isinstance(history, list):
                raise PersistenceIntegrityError("Command history must be a list")
            history.append(record)
            del history[:-MAX_HISTORY_RECORDS]

        self.store.update(append, [])
        return record

    def get_history(self):
        return self._read()

    def latest(self):
        history = self._read()

        if not history:
            return None

        return history[-1]

    def count(self):
        return len(self._read())

    def clear(self):
        self._write([])

        return {
            "success": True
        }
