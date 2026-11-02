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

    def discard(self, workflow_id):
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise ValueError("workflow_id is required")
        target = workflow_id.strip()
        def mutate(document):
            records = document.setdefault("checkpoints", [])
            before = len(records)
            records[:] = [item for item in records if item.get("workflow_id") != target]
            return before != len(records)
        return self.store.update(mutate, {"schema_version": 1, "checkpoints": []})

    def list_recent(self, limit=20):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 100:
            raise ValueError("limit must be between 0 and 100")
        records = self.store.read({"schema_version": 1, "checkpoints": []}).get("checkpoints", [])
        return list(reversed(records[-limit:]))

    def summary(self):
        records = self.store.read({"schema_version": 1, "checkpoints": []}).get("checkpoints", [])
        stages = {}
        for item in records:
            stage = str(item.get("stage") or "unknown")
            stages[stage] = stages.get(stage, 0) + 1
        return {
            "total": len(records),
            "capacity": 200,
            "stages": stages,
            "latest": records[-1] if records else None,
        }

    def resume(self, workflow_id):
        document = self.store.read({"schema_version": 1, "checkpoints": []})
        for item in reversed(document.get("checkpoints", [])):
            if item.get("workflow_id") == workflow_id:
                return item
        return None
