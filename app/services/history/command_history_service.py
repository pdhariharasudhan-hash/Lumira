from pathlib import Path
from datetime import datetime
import json


class CommandHistoryService:

    def __init__(self):
        self.history_file = Path(
            "memory/command_history.json"
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
        request_id: str,
        execution_id: str,
        session_id: str,
        project_id: str,
        message: str,
        environment: str,
        workspace: str,
        metadata: dict,
    ):
        history = self._read()

        record = {
            "request_id": request_id,
            "execution_id": execution_id,
            "session_id": session_id,
            "project_id": project_id,
            "message": message,
            "environment": environment,
            "workspace": workspace,
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat(),
        }

        history.append(record)
        self._write(history)

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
