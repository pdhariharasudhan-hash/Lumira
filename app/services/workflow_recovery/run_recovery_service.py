from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
import json

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.sessions.session_manager_service import redact_sensitive_text, redact_sensitive_value


RUN_STORE_SCHEMA_VERSION = 1
RUN_STATUSES = {"running", "failed", "completed", "blocked"}
SIDE_EFFECT_STAGES = {
    "save_project",
    "save_artifact",
    "generate_image",
    "capture_audio",
    "transcribe",
    "summarize",
    "apply_changes",
}


class RunRecoveryService:
    MAX_RUNS = 500
    MAX_STEPS = 12
    MAX_RESULT_CHARS = 300_000
    MAX_RESUMES = 3

    def __init__(self, path: str | Path = "memory/workflow_runs.json"):
        self.store = AtomicJsonStore(path)
        if not Path(path).exists():
            self.store.write({"schema_version": RUN_STORE_SCHEMA_VERSION, "runs": []})

    @staticmethod
    def _validate_document(document: object) -> dict:
        if not isinstance(document, dict) or document.get("schema_version") != RUN_STORE_SCHEMA_VERSION:
            raise PersistenceIntegrityError("Unsupported workflow run store schema")
        runs = document.get("runs")
        if not isinstance(runs, list):
            raise PersistenceIntegrityError("Workflow run store must contain a runs list")
        for run in runs:
            if not isinstance(run, dict) or run.get("status") not in RUN_STATUSES:
                raise PersistenceIntegrityError("Workflow run record is invalid")
            if not isinstance(run.get("steps"), list) or len(run["steps"]) > RunRecoveryService.MAX_STEPS:
                raise PersistenceIntegrityError("Workflow run contains an invalid step list")
            if any(not isinstance(step, str) or not step or len(step) > 80 for step in run["steps"]):
                raise PersistenceIntegrityError("Workflow run contains an invalid step name")
            if not isinstance(run.get("stage_records"), list):
                raise PersistenceIntegrityError("Workflow run stage records are invalid")
        return document

    def create_run(self, goal: str, plan: dict, session_id: str | None = None) -> dict:
        steps = plan.get("steps") if isinstance(plan, dict) else None
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 10_000:
            raise ValueError("Run goal must contain 1 to 10000 characters")
        if not isinstance(plan, dict) or not isinstance(steps, list) or not 1 <= len(steps) <= self.MAX_STEPS:
            raise ValueError("Workflow plan must contain 1 to 12 steps")
        if any(not isinstance(step, str) or not step or len(step) > 80 for step in steps):
            raise ValueError("Workflow plan contains an invalid step")
        now = datetime.now(UTC).isoformat()
        run = {
            "run_id": str(uuid4()),
            "owner_id": "local",
            "session_id": session_id,
            "goal": redact_sensitive_text(goal.strip()),
            "plan": redact_sensitive_value(plan),
            "steps": list(steps),
            "status": "running",
            "current_stage": None,
            "last_completed_stage": None,
            "stage_records": [],
            "error": None,
            "retry_count": 0,
            "resume_count": 0,
            "resume_allowed": True,
            "safe_resume_point": steps[0],
            "created_at": now,
            "updated_at": now,
            "schema_version": RUN_STORE_SCHEMA_VERSION,
        }

        def append(document):
            self._validate_document(document)
            document["runs"].append(run)
            document["runs"] = document["runs"][-self.MAX_RUNS:]
            return deepcopy(run)

        return self.store.update(append, {"schema_version": RUN_STORE_SCHEMA_VERSION, "runs": []})

    def get_run(self, run_id: str) -> dict | None:
        document = self._validate_document(self.store.read({"schema_version": RUN_STORE_SCHEMA_VERSION, "runs": []}))
        record = next((item for item in document["runs"] if item.get("run_id") == run_id), None)
        if record is None:
            return None
        run = deepcopy(record)
        if run["status"] == "running" and run.get("current_stage"):
            run["recovery_state"] = "interrupted_or_in_progress"
            run["safe_resume_point"] = self._next_safe_stage(run)
            run["resume_allowed"] = run["safe_resume_point"] is not None
        else:
            run["recovery_state"] = run["status"]
        return run

    def list_runs(self, limit: int = 50) -> list[dict]:
        if not 0 <= limit <= 200:
            raise ValueError("limit must be between 0 and 200")
        document = self._validate_document(self.store.read({"schema_version": RUN_STORE_SCHEMA_VERSION, "runs": []}))
        if limit == 0:
            return []
        return [self.get_run(item["run_id"]) for item in reversed(document["runs"][-limit:])]

    @staticmethod
    def _next_safe_stage(run: dict) -> str | None:
        completed = {item["stage"] for item in run["stage_records"] if item.get("status") == "completed"}
        current = run.get("current_stage")
        current_record = next((item for item in run["stage_records"] if item.get("stage") == current), None)
        if current_record and current_record.get("status") in {"running", "failed"} and current in SIDE_EFFECT_STAGES:
            return None
        for step in run["steps"]:
            if step not in completed:
                return step
        return None

    def update(self, run_id: str, action: str, **values) -> dict:
        updated = {}

        def mutate(document):
            self._validate_document(document)
            run = next((item for item in document["runs"] if item.get("run_id") == run_id), None)
            if run is None:
                raise KeyError("run not found")
            now = datetime.now(UTC).isoformat()
            if action == "start_stage":
                stage = values["stage"]
                record = next((item for item in run["stage_records"] if item.get("stage") == stage), None)
                if record is None:
                    record = {"stage": stage, "status": "running", "attempts": 1, "result": None, "error": None, "updated_at": now}
                    run["stage_records"].append(record)
                else:
                    record.update(status="running", attempts=int(record.get("attempts", 0)) + 1, error=None, updated_at=now)
                run.update(status="running", current_stage=stage, updated_at=now)
            elif action in {"complete_stage", "fail_stage"}:
                stage = values["stage"]
                record = next((item for item in run["stage_records"] if item.get("stage") == stage), None)
                if record is None:
                    raise PersistenceIntegrityError("Cannot close a workflow stage that was not started")
                if action == "complete_stage":
                    result = redact_sensitive_value(values.get("result"))
                    if len(json.dumps(result, ensure_ascii=False, default=str)) > self.MAX_RESULT_CHARS:
                        raise ValueError("Workflow stage result exceeds the persistence limit")
                    record.update(status="completed", result=result, error=None, updated_at=now)
                    run.update(last_completed_stage=stage, error=None)
                else:
                    run.update(status="failed", error=redact_sensitive_text(str(values.get("error") or "stage_failed")))
                    record.update(status="failed", error=run["error"], updated_at=now)
                run.update(current_stage=stage, updated_at=now)
            elif action == "resume":
                if run.get("resume_count", 0) >= self.MAX_RESUMES:
                    raise ValueError("Workflow resume limit reached")
                run.update(status="running", resume_count=run.get("resume_count", 0) + 1, retry_count=run.get("retry_count", 0) + 1, updated_at=now)
            elif action == "complete_run":
                run.update(status="completed", current_stage=None, last_completed_stage=values.get("last_completed_stage"), error=None, resume_allowed=False, updated_at=now)
            elif action == "block":
                run.update(status="blocked", resume_allowed=False, error=redact_sensitive_text(str(values.get("error") or "manual_reconciliation_required")), updated_at=now)
            else:
                raise ValueError("Unknown workflow recovery action")
            run["safe_resume_point"] = self._next_safe_stage(run)
            updated.update(deepcopy(run))
            return True

        self.store.update(mutate, {"schema_version": RUN_STORE_SCHEMA_VERSION, "runs": []})
        return updated
