from app.agents.workflow_engine import WorkflowEngine
from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.sessions.session_manager_service import SessionManagerService
from app.services.workflow_recovery.run_recovery_service import RunRecoveryService
from app.services.sessions.session_manager_service import redact_sensitive_value
import time


class FixedPlanner:
    def execute(self, goal):
        return {"success": True, "steps": ["search", "builder", "save_project"]}


class RecoverableRouter:
    def __init__(self):
        self.calls = {"search": 0, "builder": 0, "save_project": 0}

    def execute_step(self, step, goal, context):
        self.calls[step] += 1
        if step == "search":
            return {"success": True, "results": ["local result"]}
        if step == "builder" and self.calls[step] == 1:
            return {"success": False, "status": "refine", "message": "needs refinement"}
        if step == "builder":
            return {"success": True, "status": "accept", "builder": "ready"}
        return {"success": True, "saved": "project/v1"}


def blocking_worker(step, goal, context, output):
    time.sleep(5)
    output.put({"ok": True, "result": {"success": True}})


class SearchPlanner:
    def execute(self, goal):
        return {"success": True, "steps": ["search"]}


def test_non_object_capability_result_fails_stage_closed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class InvalidResultRouter:
        def execute_step(self, step, goal, context):
            return None

    recovery = RunRecoveryService()
    result = WorkflowEngine(
        planner=SearchPlanner(),
        router=InvalidResultRouter(),
        recovery=recovery,
    ).execute("Search local project files")

    assert result["success"] is False
    assert result["failed_step"] == "search"
    assert result["failure"]["code"] == "invalid_capability_result"
    run = recovery.get_run(result["run_id"])
    assert run["status"] == "failed"
    assert run["stage_records"][0]["status"] == "failed"


def test_resume_blocks_persisted_plan_checkpoint_mismatch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recovery = RunRecoveryService()
    run = recovery.create_run(
        "Search local project files",
        {"success": True, "steps": ["search"]},
    )

    def corrupt_plan(document):
        record = next(item for item in document["runs"] if item["run_id"] == run["run_id"])
        record["plan"]["steps"] = ["validate"]
        return document

    recovery.store.update(corrupt_plan)

    class MustNotExecuteRouter:
        def execute_step(self, step, goal, context):
            raise AssertionError("a corrupted workflow plan must not execute")

    result = WorkflowEngine(
        planner=SearchPlanner(),
        router=MustNotExecuteRouter(),
        recovery=recovery,
    ).resume(run["run_id"])

    assert result["state"] == "blocked"
    assert result["code"] == "persisted_plan_invalid"
    assert "No stages were resumed" in result["message"]

    # The invalid record must remain untouched: rewriting a corrupted store
    # merely to persist a blocked status would weaken the integrity boundary.
    persisted = recovery.store.read({"schema_version": 1, "runs": []})
    record = next(item for item in persisted["runs"] if item["run_id"] == run["run_id"])
    assert record["status"] == "running"
    assert record["plan"]["steps"] == ["validate"]


def test_workflow_resume_skips_completed_stages_and_persists_outcome(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recovery = RunRecoveryService()
    router = RecoverableRouter()
    engine = WorkflowEngine(planner=FixedPlanner(), router=router, recovery=recovery)

    first = engine.execute("Build the project")
    assert first["success"] is False
    assert first["failed_step"] == "builder"
    run = engine.inspect(first["run_id"])
    assert run["current_stage"] == "builder"
    assert run["last_completed_stage"] == "search"
    assert run["retry_count"] == 0

    resumed = WorkflowEngine(planner=FixedPlanner(), router=router, recovery=RunRecoveryService()).resume(first["run_id"])
    assert resumed["success"] is True
    assert resumed["retry_count"] == 1
    assert router.calls == {"search": 1, "builder": 2, "save_project": 1}
    assert engine.inspect(first["run_id"])["status"] == "completed"


def test_interrupted_irreversible_stage_requires_reconciliation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recovery = RunRecoveryService()
    run = recovery.create_run(
        "Build a project",
        {"success": True, "steps": ["search", "save_project"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="search")
    recovery.update(run["run_id"], "complete_stage", stage="search", result={"success": True})
    recovery.update(run["run_id"], "start_stage", stage="save_project")

    engine = WorkflowEngine(planner=FixedPlanner(), router=RecoverableRouter(), recovery=recovery)
    state = engine.inspect(run["run_id"])
    assert state["current_stage"] == "save_project"
    assert state["last_completed_stage"] == "search"
    assert state["resume_allowed"] is False
    result = engine.resume(run["run_id"])
    assert result["code"] == "manual_reconciliation_required"
    assert recovery.get_run(run["run_id"])["status"] == "blocked"


def test_closed_session_cannot_resume_a_workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sessions = SessionManagerService()
    session = sessions.create_session()
    sessions.close_session(session["session_id"])
    recovery = RunRecoveryService()
    run = recovery.create_run(
        "Find local project files",
        {"success": True, "steps": ["search"]},
        session_id=session["session_id"],
    )
    recovery.update(run["run_id"], "start_stage", stage="search")

    result = WorkflowEngine(planner=FixedPlanner(), router=RecoverableRouter(), recovery=recovery).resume(run["run_id"])
    assert result["code"] == "session_closed"


def test_corrupt_workflow_run_store_is_not_silently_reset(tmp_path):
    path = tmp_path / "workflow_runs.json"
    path.write_text("{broken", encoding="utf-8")
    try:
        RunRecoveryService(path).list_runs()
    except PersistenceIntegrityError:
        pass
    else:
        raise AssertionError("corrupt workflow run state was accepted")
    assert path.read_text(encoding="utf-8") == "{broken"


def test_recovery_rejects_malformed_persisted_stage_records(tmp_path):
    import json

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    run = recovery.create_run("Validate recovery integrity", {"steps": ["validate", "search"]})
    recovery.update(run["run_id"], "start_stage", stage="validate")

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["stage_records"][0]["stage"] = "unplanned_stage"
    path.write_text(json.dumps(document), encoding="utf-8")

    try:
        RunRecoveryService(path).list_runs()
    except PersistenceIntegrityError as exc:
        assert "stage record" in str(exc)
    else:
        raise AssertionError("malformed persisted stage record was accepted")


def test_capability_timeout_terminates_the_worker_process(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class SearchPlanner:
        def execute(self, goal):
            return {"success": True, "steps": ["search"]}

    engine = WorkflowEngine(
        planner=SearchPlanner(),
        recovery=RunRecoveryService(),
        timeout_seconds=0.2,
        worker_target=blocking_worker,
    )
    result = engine.execute("Search the workspace")
    assert result["success"] is False
    assert result["failure"]["code"] == "capability_timeout"
    assert not WorkflowEngine._active_processes


def test_default_workflow_executes_allowlisted_capability_in_child_process(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = WorkflowEngine(
        planner=SearchPlanner(),
        recovery=RunRecoveryService(),
        timeout_seconds=10,
    ).execute("Search local Lumira records")

    assert result["success"] is True
    assert result["state"] == "completed"
    assert result["results"][0]["success"] is True
    assert result["last_completed_stage"] == "search"


def test_credential_redaction_preserves_python_source_integrity():
    source = '''
from fastapi import Depends, Header

JWT_SECRET = "private-test-value"

def get_current_user(authorization: Header = Depends()):
    return authorization
'''
    safe = redact_sensitive_value({"files": {"main.py": source}})["files"]["main.py"]

    compile(safe, "generated_main.py", "exec")
    assert "private-test-value" not in safe
    assert "authorization: Header" in safe


def test_workflow_save_artifact_persists_redacted_result_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from app.agents.workflow_step_router import WorkflowStepRouter
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    result = WorkflowStepRouter().execute_step(
        "save_artifact",
        "Summarize the completed search",
        {"search": {"success": True, "results": ["local result"], "api_key": "artifact-secret-value"}},
    )

    assert result["success"] is True
    assert result["artifact"]["type"] == "reports"
    artifact = ArtifactManagerService().get_artifact(result["artifact"]["artifact_id"])
    assert artifact is not None
    assert artifact["source"] == "workflow_engine"
    from pathlib import Path
    saved_content = Path(artifact["file"]).read_text(encoding="utf-8")
    assert "artifact-secret-value" not in saved_content


def test_workflow_rejects_non_boolean_planner_success_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class MalformedPlanner:
        def execute(self, goal):
            return {"success": "false", "steps": ["search"]}

    recovery = RunRecoveryService()
    result = WorkflowEngine(planner=MalformedPlanner(), recovery=recovery).execute(
        "Search safely"
    )

    assert result["success"] is False
    assert result["code"] == "planning_failed"
    assert recovery.list_runs() == []


def test_workflow_planner_exception_returns_stable_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class BrokenPlanner:
        def execute(self, goal):
            raise RuntimeError("provider detail must not leak")

    recovery = RunRecoveryService()
    result = WorkflowEngine(planner=BrokenPlanner(), recovery=recovery).execute(
        "Search safely"
    )

    assert result["success"] is False
    assert result["code"] == "planning_failed"
    assert result["error_type"] == "RuntimeError"
    assert "provider detail" not in str(result)
    assert recovery.list_runs() == []


def test_workflow_rejects_duplicate_plan_stages_before_persistence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class DuplicatePlanner:
        def execute(self, goal):
            return {"success": True, "steps": ["search", "search"], "api_key": "test-secret-value"}

    recovery = RunRecoveryService()
    result = WorkflowEngine(planner=DuplicatePlanner(), recovery=recovery).execute(
        "Search once"
    )

    assert result["success"] is False
    assert result["code"] == "invalid_plan"
    assert "duplicate" in result["message"]
    assert "test-secret-value" not in str(result)
    assert recovery.list_runs() == []


def test_workflow_rejects_unimplemented_interactive_audio_capture():
    class AudioCapturePlanner:
        def execute(self, goal):
            return {"success": True, "steps": ["capture_audio"]}

    class MustNotExecuteRouter:
        def execute_step(self, step, goal, context):
            raise AssertionError("unsupported interactive stage must not execute")

    result = WorkflowEngine(
        planner=AudioCapturePlanner(),
        router=MustNotExecuteRouter(),
    ).execute("Capture audio from the microphone")

    assert result["success"] is False
    assert result["code"] == "capability_unavailable"
    assert result["unsupported_steps"] == ["capture_audio"]


def test_recovery_rejects_unknown_or_out_of_order_stages(tmp_path):
    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    run = recovery.create_run("Build safely", {"steps": ["validate", "generate_code"]})

    import pytest
    with pytest.raises(ValueError, match="not in the workflow plan"):
        recovery.update(run["run_id"], "start_stage", stage="run_shell")
    with pytest.raises(ValueError, match="plan order"):
        recovery.update(run["run_id"], "start_stage", stage="generate_code")

    assert recovery.get_run(run["run_id"])["stage_records"] == []


def test_recovery_requires_current_running_stage_and_all_steps_before_completion(tmp_path):
    import pytest

    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    run = recovery.create_run("Build safely", {"steps": ["validate", "generate_code"]})

    with pytest.raises(ValueError, match="every planned stage"):
        recovery.update(run["run_id"], "complete_run", last_completed_stage="generate_code")
    recovery.update(run["run_id"], "start_stage", stage="validate")
    with pytest.raises(ValueError, match="already running"):
        recovery.update(run["run_id"], "start_stage", stage="validate")
    recovery.update(run["run_id"], "complete_stage", stage="validate", result={"ok": True})
    recovery.update(run["run_id"], "start_stage", stage="generate_code")
    with pytest.raises(ValueError, match="currently running"):
        recovery.update(run["run_id"], "complete_stage", stage="validate", result={"ok": True})

    with pytest.raises(ValueError, match="every planned stage"):
        recovery.update(run["run_id"], "complete_run", last_completed_stage="generate_code")


def test_recovery_rejects_duplicate_plan_stages(tmp_path):
    import pytest

    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    with pytest.raises(ValueError, match="duplicate steps"):
        recovery.create_run("Build safely", {"steps": ["validate", "validate"]})


def test_blocked_run_cannot_be_bypassed_with_new_recovery_window(tmp_path):
    import pytest

    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    run = recovery.create_run(
        "Recover only after review",
        {"steps": ["validate", "builder", "save_project"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="validate")
    recovery.update(run["run_id"], "complete_stage", stage="validate", result={"valid": True})
    recovery.update(run["run_id"], "start_stage", stage="builder")
    recovery.update(run["run_id"], "fail_stage", stage="builder", error="needs review")
    recovery.update(run["run_id"], "block", error="manual review required")

    blocked = recovery.get_run(run["run_id"])
    assert blocked["status"] == "blocked"
    assert blocked["resume_allowed"] is False
    with pytest.raises(ValueError, match="must be running"):
        recovery.update(run["run_id"], "start_stage", stage="builder")
    with pytest.raises(ValueError, match="blocked or non-resumable"):
        recovery.create_recovery_window(run["run_id"])
    assert len(recovery.list_runs(limit=10)) == 1


def test_recovery_rejects_unhashable_persisted_status_values(tmp_path):
    import json
    import pytest

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    run = recovery.create_run("Validate malformed state", {"steps": ["validate"]})

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["status"] = ["running"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="invalid status"):
        recovery.list_runs()

    document["runs"][0]["status"] = "running"
    document["runs"][0]["plan"] = {"steps": ["validate"]}
    document["runs"][0]["stage_records"] = [{
        "stage": "validate", "status": ["running"], "attempts": 1, "updated_at": "now"
    }]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="invalid stage status"):
        recovery.list_runs()


def test_recovery_rejects_plan_checkpoint_mismatch_and_duplicate_run_ids(tmp_path):
    import json
    import pytest

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    run = recovery.create_run("Validate persisted plan", {"steps": ["validate"]})

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["plan"]["steps"] = ["search"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="persisted plan"):
        recovery.list_runs()

    document["runs"][0]["plan"]["steps"] = ["validate"]
    document["runs"].append(dict(document["runs"][0]))
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="duplicate run ID"):
        recovery.list_runs()



def test_recovery_rejects_checkpoint_pointer_that_hides_running_side_effect(tmp_path):
    import json

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    run = recovery.create_run(
        "Save a project exactly once",
        {"steps": ["search", "save_project"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="search")
    recovery.update(run["run_id"], "complete_stage", stage="search", result={"success": True})
    recovery.update(run["run_id"], "start_stage", stage="save_project")

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["current_stage"] = None
    path.write_text(json.dumps(document), encoding="utf-8")

    try:
        RunRecoveryService(path).get_run(run["run_id"])
    except PersistenceIntegrityError as exc:
        assert "Running stage does not match" in str(exc)
    else:
        raise AssertionError("a checkpoint that hides a running side effect was accepted")


def test_recovery_rejects_multiple_running_stage_records(tmp_path):
    import json

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    run = recovery.create_run(
        "Validate checkpoint consistency",
        {"steps": ["search", "builder"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="search")

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["stage_records"].append({
        "stage": "builder",
        "status": "running",
        "attempts": 1,
        "result": None,
        "error": None,
        "updated_at": document["runs"][0]["stage_records"][0]["updated_at"],
    })
    path.write_text(json.dumps(document), encoding="utf-8")

    try:
        RunRecoveryService(path).list_runs()
    except PersistenceIntegrityError as exc:
        assert "multiple running stages" in str(exc)
    else:
        raise AssertionError("multiple running stages were accepted")



def test_recovery_rejects_safe_resume_point_that_targets_completed_stage(tmp_path):
    import json

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    run = recovery.create_run(
        "Do not repeat a completed save",
        {"steps": ["search", "save_project", "validate"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="search")
    recovery.update(run["run_id"], "complete_stage", stage="search", result={"success": True})
    recovery.update(run["run_id"], "start_stage", stage="save_project")
    recovery.update(run["run_id"], "complete_stage", stage="save_project", result={"success": True})
    recovery.update(run["run_id"], "start_stage", stage="validate")

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["safe_resume_point"] = "save_project"
    path.write_text(json.dumps(document), encoding="utf-8")

    try:
        RunRecoveryService(path).create_recovery_window(run["run_id"])
    except PersistenceIntegrityError as exc:
        assert "safe resume point" in str(exc)
    else:
        raise AssertionError("a safe resume point targeting a completed stage was accepted")



def test_recovery_rejects_completed_stage_after_unfinished_stage(tmp_path):
    import json

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    recovery.create_run(
        "Reject impossible stage history",
        {"steps": ["search", "builder", "save_project"]},
    )
    recovery.update(
        recovery.list_runs()[0]["run_id"],
        "start_stage",
        stage="search",
    )

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["stage_records"].append({
        "stage": "builder",
        "status": "completed",
        "attempts": 1,
        "result": {"success": True},
        "error": None,
        "updated_at": document["runs"][0]["stage_records"][0]["updated_at"],
    })
    path.write_text(json.dumps(document), encoding="utf-8")

    import pytest
    with pytest.raises(PersistenceIntegrityError, match="Completed workflow stage follows"):
        recovery.list_runs()


def test_recovery_rejects_last_completed_pointer_mismatch(tmp_path):
    import json
    import pytest

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    run = recovery.create_run(
        "Reject stale completed-stage pointer",
        {"steps": ["search", "builder"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="search")
    recovery.update(
        run["run_id"],
        "complete_stage",
        stage="search",
        result={"success": True},
    )

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["last_completed_stage"] = None
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PersistenceIntegrityError, match="last completed stage"):
        recovery.list_runs()



def test_failed_stage_retry_requires_resume_and_obeys_retry_limit(tmp_path):
    import pytest

    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    run = recovery.create_run(
        "Retry only through the guarded resume path",
        {"steps": ["search", "builder"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="search")
    recovery.update(run["run_id"], "fail_stage", stage="search", error="temporary failure")

    with pytest.raises(ValueError, match="must be running"):
        recovery.update(run["run_id"], "start_stage", stage="search")

    for expected_count in range(1, recovery.MAX_RESUMES + 1):
        state = recovery.update(run["run_id"], "resume")
        assert state["resume_count"] == expected_count
        recovery.update(run["run_id"], "start_stage", stage="search")
        recovery.update(
            run["run_id"],
            "fail_stage",
            stage="search",
            error="temporary failure",
        )

    with pytest.raises(ValueError, match="resume limit"):
        recovery.update(run["run_id"], "resume")



def test_recovery_rejects_persisted_stage_records_out_of_plan_order(tmp_path):
    import json
    import pytest

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    run = recovery.create_run(
        "Reject reordered checkpoint history",
        {"steps": ["search", "builder", "validate"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="search")
    recovery.update(run["run_id"], "complete_stage", stage="search", result={"success": True})
    recovery.update(run["run_id"], "start_stage", stage="builder")
    recovery.update(run["run_id"], "complete_stage", stage="builder", result={"success": True})
    recovery.update(run["run_id"], "start_stage", stage="validate")

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["stage_records"][0], document["runs"][0]["stage_records"][1] = (
        document["runs"][0]["stage_records"][1],
        document["runs"][0]["stage_records"][0],
    )
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PersistenceIntegrityError, match="out of plan order"):
        recovery.list_runs()



def test_blocked_running_side_effect_cannot_be_closed_or_completed(tmp_path):
    import pytest

    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    run = recovery.create_run(
        "Do not finalize an uncertain side effect",
        {"steps": ["search", "save_project"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="search")
    recovery.update(
        run["run_id"],
        "complete_stage",
        stage="search",
        result={"success": True},
    )
    recovery.update(run["run_id"], "start_stage", stage="save_project")
    recovery.update(run["run_id"], "block", error="manual reconciliation required")

    with pytest.raises(ValueError, match="must be running"):
        recovery.update(
            run["run_id"],
            "complete_stage",
            stage="save_project",
            result={"success": True},
        )
    with pytest.raises(ValueError, match="must be running"):
        recovery.update(
            run["run_id"],
            "fail_stage",
            stage="save_project",
            error="reconciled",
        )
    with pytest.raises(ValueError, match="must be running"):
        recovery.update(
            run["run_id"],
            "complete_run",
            last_completed_stage="save_project",
        )

    blocked = recovery.get_run(run["run_id"])
    assert blocked["status"] == "blocked"
    assert blocked["resume_allowed"] is False
    assert blocked["stage_records"][-1]["status"] == "running"



def test_recovery_windows_cannot_branch_or_reset_bounded_retries(tmp_path):
    import pytest

    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    root = recovery.create_run("Bound recovery history", {"steps": ["search"]})
    first = recovery.create_recovery_window(root["run_id"])
    with pytest.raises(ValueError, match="already exists"):
        recovery.create_recovery_window(root["run_id"])

    second = recovery.create_recovery_window(first["run_id"])
    third = recovery.create_recovery_window(second["run_id"])
    with pytest.raises(ValueError, match="chain limit"):
        recovery.create_recovery_window(third["run_id"])

    exhausted = recovery.create_run("Do not reset exhausted retries", {"steps": ["search"]})
    for _ in range(recovery.MAX_RESUMES):
        recovery.update(exhausted["run_id"], "resume")
    with pytest.raises(ValueError, match="resume limit"):
        recovery.create_recovery_window(exhausted["run_id"])



def test_recovery_rejects_inconsistent_terminal_and_failed_status_flags(tmp_path):
    import json
    import pytest

    path = tmp_path / "workflow_runs.json"
    recovery = RunRecoveryService(path)
    failed = recovery.create_run("Reject failed state mismatch", {"steps": ["search"]})
    recovery.update(failed["run_id"], "start_stage", stage="search")
    recovery.update(failed["run_id"], "fail_stage", stage="search", error="failure")

    document = json.loads(path.read_text(encoding="utf-8"))
    document["runs"][0]["status"] = "running"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="cannot contain a failed stage"):
        recovery.list_runs()

    document["runs"][0]["status"] = "blocked"
    document["runs"][0]["resume_allowed"] = True
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="must disable resume"):
        recovery.list_runs()



def test_completed_workflow_cannot_be_reclassified_as_blocked(tmp_path):
    import pytest

    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    run = recovery.create_run("Preserve completed workflow state", {"steps": ["validate"]})
    recovery.update(run["run_id"], "start_stage", stage="validate")
    recovery.update(run["run_id"], "complete_stage", stage="validate", result={"success": True})
    recovery.update(run["run_id"], "complete_run", last_completed_stage="validate")

    with pytest.raises(ValueError, match="Completed workflow cannot be blocked"):
        recovery.update(run["run_id"], "block", error="late state change")

    persisted = recovery.get_run(run["run_id"])
    assert persisted["status"] == "completed"
    assert persisted["resume_allowed"] is False
    assert persisted["error"] is None



def test_workflow_context_redacts_secret_fields_before_next_stage(tmp_path):
    class TwoStagePlanner:
        def execute(self, goal):
            return {"success": True, "steps": ["search", "builder"]}

    class ContextInspectingRouter:
        def execute_step(self, step, goal, context):
            if step == "search":
                return {
                    "success": True,
                    "api_key": "test-secret-must-not-flow",
                    "items": ["safe result"],
                }
            if step == "builder":
                assert context["search"]["api_key"] == "[REDACTED]"
                return {
                    "success": True,
                    "status": "accept",
                    "received_key": context["search"]["api_key"],
                }
            raise AssertionError(f"Unexpected workflow stage: {step}")

    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    result = WorkflowEngine(
        planner=TwoStagePlanner(),
        router=ContextInspectingRouter(),
        recovery=recovery,
    ).execute("Search and safely process a result")

    assert result["success"] is True
    assert result["context"]["search"]["api_key"] == "[REDACTED]"
    persisted = recovery.get_run(result["run_id"])
    search_record = next(record for record in persisted["stage_records"] if record["stage"] == "search")
    assert search_record["result"]["api_key"] == "[REDACTED]"



def test_workflow_status_failure_without_success_flag_is_not_marked_completed(tmp_path):
    class SearchPlanner:
        def execute(self, goal):
            return {"success": True, "steps": ["search"]}

    class BlockedRouter:
        def execute_step(self, step, goal, context):
            return {"state": "blocked", "message": "isolation unavailable"}

    recovery = RunRecoveryService(tmp_path / "workflow_runs.json")
    result = WorkflowEngine(
        planner=SearchPlanner(),
        router=BlockedRouter(),
        recovery=recovery,
    ).execute("Run a blocked stage safely")

    assert result["success"] is False
    assert result["failed_step"] == "search"
    assert result["failure"]["state"] == "blocked"
    persisted = recovery.get_run(result["run_id"])
    assert persisted["status"] == "failed"
    assert persisted["stage_records"][0]["status"] == "failed"
