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
