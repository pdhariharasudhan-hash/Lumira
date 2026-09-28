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
    recovery.update(run["run_id"], "start_stage", stage="save_project")

    engine = WorkflowEngine(planner=FixedPlanner(), router=RecoverableRouter(), recovery=recovery)
    state = engine.inspect(run["run_id"])
    assert state["current_stage"] == "save_project"
    assert state["last_completed_stage"] is None
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
