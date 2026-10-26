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
    MAX_RECOVERY_WINDOWS = 3

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
        seen_run_ids = set()
        for run in runs:
            if not isinstance(run, dict):
                raise PersistenceIntegrityError("Workflow run record is invalid")
            run_status = run.get("status")
            if not isinstance(run_status, str) or run_status not in RUN_STATUSES:
                raise PersistenceIntegrityError("Workflow run record has an invalid status")
            run_id = run.get("run_id")
            if not isinstance(run_id, str) or not run_id or run_id in seen_run_ids:
                raise PersistenceIntegrityError("Workflow run record has an invalid or duplicate run ID")
            seen_run_ids.add(run_id)
            goal = run.get("goal")
            if not isinstance(goal, str) or not goal.strip() or len(goal) > 10_000:
                raise PersistenceIntegrityError("Workflow run record has an invalid goal")
            steps = run.get("steps")
            if not isinstance(steps, list) or not 1 <= len(steps) <= RunRecoveryService.MAX_STEPS:
                raise PersistenceIntegrityError("Workflow run contains an invalid step list")
            plan = run.get("plan")
            if not isinstance(plan, dict) or plan.get("steps") != steps:
                raise PersistenceIntegrityError("Workflow run record has an invalid persisted plan")
            if any(not isinstance(step, str) or not step or len(step) > 80 for step in run["steps"]):
                raise PersistenceIntegrityError("Workflow run contains an invalid step name")
            stage_records = run.get("stage_records")
            if not isinstance(stage_records, list) or len(stage_records) > RunRecoveryService.MAX_STEPS:
                raise PersistenceIntegrityError("Workflow run stage records are invalid")
            seen_stages = set()
            allowed_stage_statuses = {"pending", "running", "completed", "failed"}
            for record in stage_records:
                if not isinstance(record, dict):
                    raise PersistenceIntegrityError("Workflow run contains an invalid stage record")
                stage = record.get("stage")
                if not isinstance(stage, str) or stage not in run["steps"] or stage in seen_stages:
                    raise PersistenceIntegrityError("Workflow run contains an unknown or duplicate stage record")
                stage_status = record.get("status")
                if not isinstance(stage_status, str) or stage_status not in allowed_stage_statuses:
                    raise PersistenceIntegrityError("Workflow run contains an invalid stage status")
                attempts = record.get("attempts")
                if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
                    raise PersistenceIntegrityError("Workflow run contains an invalid stage attempt count")
                if not isinstance(record.get("updated_at"), str) or not record["updated_at"]:
                    raise PersistenceIntegrityError("Workflow run contains an invalid stage timestamp")
                seen_stages.add(stage)

            # Stage history is append-only and must follow the declared plan.
            # A corrupted history must not claim later work completed while an
            # earlier stage is still pending, running, or failed.
            stage_positions = [run["steps"].index(record["stage"]) for record in stage_records]
            if stage_positions != sorted(stage_positions):
                raise PersistenceIntegrityError("Workflow stage records are out of plan order")
            encountered_incomplete = False
            for record in stage_records:
                if record.get("status") == "completed":
                    if encountered_incomplete:
                        raise PersistenceIntegrityError(
                            "Completed workflow stage follows an unfinished stage"
                        )
                else:
                    encountered_incomplete = True

            completed_in_plan_order = [
                step for step in run["steps"]
                if (stage_by_name := next(
                    (item for item in stage_records if item.get("stage") == step),
                    None,
                )) is not None and stage_by_name.get("status") == "completed"
            ]
            expected_last_completed = completed_in_plan_order[-1] if completed_in_plan_order else None
            if run.get("last_completed_stage") != expected_last_completed:
                raise PersistenceIntegrityError(
                    "Workflow last completed stage does not match stage history"
                )

            # The persisted checkpoint pointer must agree with stage history.
            # Otherwise a corrupted pointer could hide an interrupted side effect
            # and allow that stage to execute twice during resume.
            stage_by_name = {record["stage"]: record for record in stage_records}
            current_stage = run.get("current_stage")
            current_record = stage_by_name.get(current_stage) if current_stage is not None else None
            if current_stage is not None and current_record is None:
                raise PersistenceIntegrityError("Workflow run current stage has no matching stage record")
            running_records = [record for record in stage_records if record.get("status") == "running"]
            failed_records = [record for record in stage_records if record.get("status") == "failed"]
            if len(running_records) > 1:
                raise PersistenceIntegrityError("Workflow run cannot have multiple running stages")
            if running_records and running_records[0].get("stage") != current_stage:
                raise PersistenceIntegrityError("Running stage does not match the workflow checkpoint")
            if len(failed_records) > 1:
                raise PersistenceIntegrityError("Workflow run cannot have multiple failed stages")
            if failed_records and failed_records[0].get("stage") != current_stage:
                raise PersistenceIntegrityError("Failed stage does not match the workflow checkpoint")
            if run_status == "running" and failed_records:
                raise PersistenceIntegrityError("Running workflow cannot contain a failed stage")
            if run_status in {"blocked", "completed"} and run.get("resume_allowed") is not False:
                raise PersistenceIntegrityError("Blocked or completed workflow must disable resume")
            if run_status == "completed":
                if current_stage is not None:
                    raise PersistenceIntegrityError("Completed workflow cannot have a current stage")
                completed_names = {record["stage"] for record in stage_records if record.get("status") == "completed"}
                if completed_names != set(run["steps"]):
                    raise PersistenceIntegrityError("Completed workflow has unfinished stages")
            if run_status == "failed" and (
                current_record is None or current_record.get("status") != "failed"
            ):
                raise PersistenceIntegrityError("Failed workflow has no matching failed stage")
            if current_record is not None and current_record.get("status") == "pending":
                raise PersistenceIntegrityError("Workflow current stage cannot be pending")
            expected_safe_resume_point = RunRecoveryService._next_safe_stage(run)
            if run.get("safe_resume_point") != expected_safe_resume_point:
                raise PersistenceIntegrityError("Workflow safe resume point does not match stage history")

            if len(set(run["steps"])) != len(run["steps"]):
                raise PersistenceIntegrityError("Workflow run contains duplicate planned steps")
            for field in ("current_stage", "last_completed_stage", "safe_resume_point"):
                value = run.get(field)
                if value is not None and (not isinstance(value, str) or value not in run["steps"]):
                    raise PersistenceIntegrityError(f"Workflow run contains an invalid {field}")
            for field in ("retry_count", "resume_count"):
                value = run.get(field, 0)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise PersistenceIntegrityError(f"Workflow run contains an invalid {field}")
            if "resume_allowed" in run and not isinstance(run["resume_allowed"], bool):
                raise PersistenceIntegrityError("Workflow run contains an invalid resume_allowed flag")
        return document

    def create_run(self, goal: str, plan: dict, session_id: str | None = None) -> dict:
        steps = plan.get("steps") if isinstance(plan, dict) else None
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 10_000:
            raise ValueError("Run goal must contain 1 to 10000 characters")
        if not isinstance(plan, dict) or not isinstance(steps, list) or not 1 <= len(steps) <= self.MAX_STEPS:
            raise ValueError("Workflow plan must contain 1 to 12 steps")
        if any(not isinstance(step, str) or not step or len(step) > 80 for step in steps):
            raise ValueError("Workflow plan contains an invalid step")
        if len(set(steps)) != len(steps):
            raise ValueError("Workflow plan cannot contain duplicate steps")
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

    def create_recovery_window(self, run_id: str) -> dict:
        """
        Create a new bounded recovery run from an existing safe checkpoint.

        The original recovery run is preserved unchanged. The new run inherits
        the durable workflow plan, goal, session, completed stages, and safe
        resume point, but starts with a fresh bounded resume budget.
        """
        source = self.get_run(run_id)
        if source is None:
            raise KeyError("recovery run not found")

        if source.get("status") == "completed":
            raise ValueError("Cannot create a recovery window from a completed run")
        if source.get("status") == "blocked" or source.get("resume_allowed") is False:
            raise ValueError("Cannot create a recovery window from a blocked or non-resumable run")
        if source.get("resume_count", 0) >= self.MAX_RESUMES:
            raise ValueError("Cannot create a recovery window after the resume limit is reached")

        safe_resume_point = source.get("safe_resume_point")
        if not safe_resume_point:
            raise ValueError(
                "Cannot create a recovery window without a safe resume point"
            )

        now = datetime.now(UTC).isoformat()
        inherited_records = deepcopy(source.get("stage_records", []))

        # A failed/running stage must not remain active in the new window.
        for record in inherited_records:
            if record.get("stage") == safe_resume_point:
                record["status"] = "pending"
                record["error"] = None
                record["result"] = None
                record["updated_at"] = now

        new_run = {
            "run_id": str(uuid4()),
            "owner_id": source.get("owner_id", "local"),
            "session_id": source.get("session_id"),
            "goal": source["goal"],
            "plan": deepcopy(source["plan"]),
            "steps": list(source["steps"]),
            "status": "running",
            "current_stage": None,
            "last_completed_stage": source.get("last_completed_stage"),
            "stage_records": inherited_records,
            "error": None,
            "retry_count": 0,
            "resume_count": 0,
            "resume_allowed": True,
            "safe_resume_point": safe_resume_point,
            "created_at": now,
            "updated_at": now,
            "schema_version": RUN_STORE_SCHEMA_VERSION,
            "recovery_parent_run_id": source["run_id"],
            "recovery_window": True,
        }

        def append(document):
            self._validate_document(document)
            existing_runs = document["runs"]
            if any(item.get("recovery_parent_run_id") == run_id for item in existing_runs):
                raise ValueError("A recovery window already exists for this run")

            run_by_id = {item["run_id"]: item for item in existing_runs}
            cursor = run_by_id.get(run_id)
            ancestry_depth = 0
            seen_ancestors = set()
            while cursor and cursor.get("recovery_parent_run_id"):
                parent_id = cursor["recovery_parent_run_id"]
                if parent_id in seen_ancestors:
                    raise PersistenceIntegrityError("Recovery window ancestry contains a cycle")
                seen_ancestors.add(parent_id)
                ancestry_depth += 1
                cursor = run_by_id.get(parent_id)
            if ancestry_depth >= self.MAX_RECOVERY_WINDOWS:
                raise ValueError("Recovery window chain limit reached")

            existing_runs.append(new_run)
            document["runs"] = existing_runs[-self.MAX_RUNS:]
            return deepcopy(new_run)

        return self.store.update(
            append,
            {"schema_version": RUN_STORE_SCHEMA_VERSION, "runs": []},
        )

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
                if run.get("status") != "running":
                    raise ValueError("Workflow run must be running before a stage can start")
                if run.get("resume_allowed") is False:
                    raise ValueError("Workflow run is not marked safe to resume")
                stage = values["stage"]
                if stage not in run["steps"]:
                    raise ValueError("Cannot start a stage that is not in the workflow plan")
                completed = {item["stage"] for item in run["stage_records"] if item.get("status") == "completed"}
                expected_stage = next((step for step in run["steps"] if step not in completed), None)
                if stage != expected_stage:
                    raise ValueError("Workflow stages must start in plan order and cannot restart completed stages")
                if run.get("current_stage") and run.get("current_stage") != stage:
                    current = next((item for item in run["stage_records"] if item.get("stage") == run.get("current_stage")), None)
                    if current and current.get("status") == "running":
                        raise ValueError("Cannot start a stage while another stage is running")
                record = next((item for item in run["stage_records"] if item.get("stage") == stage), None)
                if record is not None and record.get("status") == "running":
                    raise ValueError("Workflow stage is already running")
                if record is None:
                    record = {"stage": stage, "status": "running", "attempts": 1, "result": None, "error": None, "updated_at": now}
                    run["stage_records"].append(record)
                else:
                    record.update(status="running", attempts=int(record.get("attempts", 0)) + 1, error=None, updated_at=now)
                run.update(status="running", current_stage=stage, updated_at=now)
            elif action in {"complete_stage", "fail_stage"}:
                if run.get("status") != "running":
                    raise ValueError("Workflow run must be running to close a stage")
                if run.get("resume_allowed") is False:
                    raise ValueError("Workflow run is not marked safe to resume")
                stage = values["stage"]
                record = next((item for item in run["stage_records"] if item.get("stage") == stage), None)
                if record is None:
                    raise PersistenceIntegrityError("Cannot close a workflow stage that was not started")
                if run.get("current_stage") != stage or record.get("status") != "running":
                    raise ValueError("Only the currently running workflow stage can be completed or failed")
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
                if run.get("status") in {"completed", "blocked"}:
                    raise ValueError("Workflow run cannot be resumed from its current status")
                if run.get("resume_allowed") is False:
                    raise ValueError("Workflow run is not marked safe to resume")
                if self._next_safe_stage(run) is None:
                    raise ValueError("Workflow run has no safe resume point")
                if run.get("resume_count", 0) >= self.MAX_RESUMES:
                    raise ValueError("Workflow resume limit reached")
                current_stage = run.get("current_stage")
                current_record = next(
                    (item for item in run["stage_records"] if item.get("stage") == current_stage),
                    None,
                )
                if current_record and current_record.get("status") in {"running", "failed"}:
                    # Retrying is allowed only for reversible stages. Mark the
                    # interrupted stage pending so start_stage can reject duplicate
                    # starts while an actual attempt is still running.
                    if current_stage in SIDE_EFFECT_STAGES:
                        raise ValueError("Workflow stage requires manual reconciliation")
                    current_record.update(
                        status="pending",
                        result=None,
                        error=None,
                        updated_at=now,
                    )
                    run["current_stage"] = None
                run.update(
                    status="running",
                    resume_count=run.get("resume_count", 0) + 1,
                    retry_count=run.get("retry_count", 0) + 1,
                    updated_at=now,
                )
            elif action == "complete_run":
                if run.get("status") != "running":
                    raise ValueError("Workflow run must be running before completion")
                if run.get("resume_allowed") is False:
                    raise ValueError("Workflow run is not marked safe to resume")
                completed = {item["stage"] for item in run["stage_records"] if item.get("status") == "completed"}
                if completed != set(run["steps"]):
                    raise ValueError("Cannot complete a workflow before every planned stage is completed")
                if values.get("last_completed_stage") != run["steps"][-1]:
                    raise ValueError("Completed workflow stage does not match the plan")
                run.update(status="completed", current_stage=None, last_completed_stage=values.get("last_completed_stage"), error=None, resume_allowed=False, updated_at=now)
            elif action == "block":
                if run.get("status") == "completed":
                    raise ValueError("Completed workflow cannot be blocked")
                run.update(status="blocked", resume_allowed=False, error=redact_sensitive_text(str(values.get("error") or "manual_reconciliation_required")), updated_at=now)
            else:
                raise ValueError("Unknown workflow recovery action")
            run["safe_resume_point"] = self._next_safe_stage(run)
            updated.update(deepcopy(run))
            return True

        self.store.update(mutate, {"schema_version": RUN_STORE_SCHEMA_VERSION, "runs": []})
        return updated
