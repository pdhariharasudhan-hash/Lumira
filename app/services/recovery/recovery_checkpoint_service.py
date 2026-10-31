from pathlib import Path
from datetime import UTC, datetime
from app.services.persistence.atomic_json_store import AtomicJsonStore

class RecoveryCheckpointService:
    """Durable bounded checkpoints for interrupted personal workflows."""
    def __init__(self, path="memory/recovery_checkpoints.json"):
        self.store = AtomicJsonStore(path)
        if not Path(path).exists():
            self.store.write({"schema_version": 1, "checkpoints": []})

    def save(self, workflow_id, stage, state):
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise ValueError("workflow_id is required")
        if not isinstance(stage, str) or not stage.strip() or len(stage) > 128:
            raise ValueError("stage must be 1 to 128 characters")
        if not isinstance(state, dict):
            raise ValueError("state must be an object")
        record = {"workflow_id": workflow_id.strip(), "stage": stage.strip(), "state": state, "updated_at": datetime.now(UTC).isoformat()}
        def mutate(document):
            records = document.setdefault("checkpoints", [])
            records[:] = [item for item in records if item.get("workflow_id") != record["workflow_id"]]
            records.append(record)
            document["checkpoints"] = records[-200:]
            return record
        return self.store.update(mutate, {"schema_version": 1, "checkpoints": []})

    def resume(self, workflow_id):
        document = self.store.read({"schema_version": 1, "checkpoints": []})
        for item in reversed(document.get("checkpoints", [])):
            if item.get("workflow_id") == workflow_id:
                return item
        return None
