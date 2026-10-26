import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.workflow_recovery.run_recovery_service import RunRecoveryService


def test_recovery_routes_are_registered():
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/recovery/runs" in paths
    assert "/recovery/runs/{run_id}" in paths
    assert "/recovery/runs/{run_id}/window" in paths
    assert "/recovery/runs/{run_id}/resume" in paths


def test_recovery_api_inspects_runs_and_creates_safe_window(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = RunRecoveryService()
    original = service.create_run(
        "Build a safe test project",
        {"steps": ["validate", "generate_code", "save_project"]},
        session_id="session-test",
    )
    service.update(original["run_id"], "start_stage", stage="validate")
    service.update(original["run_id"], "complete_stage", stage="validate", result={"valid": True})
    service.update(original["run_id"], "start_stage", stage="generate_code")
    service.update(original["run_id"], "fail_stage", stage="generate_code", error="provider failed")

    client = TestClient(app)
    listing = client.get("/recovery/runs?limit=10")
    assert listing.status_code == 200
    assert any(item["run_id"] == original["run_id"] for item in listing.json()["runs"])

    detail = client.get(f"/recovery/runs/{original['run_id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "failed"

    response = client.post(f"/recovery/runs/{original['run_id']}/window")
    assert response.status_code == 201
    recovered = response.json()
    assert recovered["recovery_parent_run_id"] == original["run_id"]
    assert recovered["recovery_window"] is True
    assert recovered["safe_resume_point"] == "generate_code"
    assert recovered["status"] == "running"

    unchanged = client.get(f"/recovery/runs/{original['run_id']}")
    assert unchanged.status_code == 200
    assert unchanged.json()["status"] == "failed"


def test_recovery_api_reports_missing_runs_and_bounds_limit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    assert client.get("/recovery/runs/not-a-run").status_code == 404
    assert client.post("/recovery/runs/not-a-run/resume").status_code == 404
    assert client.get("/recovery/runs?limit=201").status_code == 422


def test_resume_endpoint_invokes_guarded_workflow_engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recovery = RunRecoveryService()
    run = recovery.create_run("Resume a safe search", {"success": True, "steps": ["search"]})
    observed = {}

    class FakeWorkflowEngine:
        def __init__(self, recovery):
            observed["recovery"] = recovery

        def resume(self, run_id):
            observed["run_id"] = run_id
            return {"success": True, "state": "completed", "run_id": run_id}

    monkeypatch.setattr("app.routes.recovery.WorkflowEngine", FakeWorkflowEngine)
    response = TestClient(app).post(f"/recovery/runs/{run['run_id']}/resume")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert observed["run_id"] == run["run_id"]
    assert isinstance(observed["recovery"], RunRecoveryService)


def test_resume_endpoint_blocks_unknown_side_effect_outcome(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recovery = RunRecoveryService()
    run = recovery.create_run(
        "Save a project once",
        {"success": True, "steps": ["search", "save_project"]},
    )
    recovery.update(run["run_id"], "start_stage", stage="search")
    recovery.update(run["run_id"], "complete_stage", stage="search", result={"success": True})
    recovery.update(run["run_id"], "start_stage", stage="save_project")

    response = TestClient(app).post(f"/recovery/runs/{run['run_id']}/resume")
    assert response.status_code == 200
    assert response.json()["code"] == "manual_reconciliation_required"
    assert RunRecoveryService().get_run(run["run_id"])["status"] == "blocked"


def test_recovery_service_refuses_unsafe_or_terminal_resume_states(tmp_path):
    service = RunRecoveryService(tmp_path / "workflow_runs.json")

    side_effect = service.create_run(
        "Apply a change once",
        {"steps": ["apply_changes", "validate"]},
    )
    service.update(side_effect["run_id"], "start_stage", stage="apply_changes")
    with pytest.raises(ValueError, match="safe resume point"):
        service.update(side_effect["run_id"], "resume")
    unchanged = service.get_run(side_effect["run_id"])
    assert unchanged["status"] == "running"
    assert unchanged["resume_count"] == 0
    assert unchanged["safe_resume_point"] is None

    completed = service.create_run(
        "Already finished",
        {"steps": ["validate"]},
    )
    service.update(completed["run_id"], "start_stage", stage="validate")
    service.update(completed["run_id"], "complete_stage", stage="validate", result={"ok": True})
    service.update(completed["run_id"], "complete_run", last_completed_stage="validate")
    with pytest.raises(ValueError, match="current status"):
        service.update(completed["run_id"], "resume")

    blocked = service.create_run(
        "Needs manual review",
        {"steps": ["validate"]},
    )
    service.update(blocked["run_id"], "block", error="manual review required")
    with pytest.raises(ValueError, match="current status"):
        service.update(blocked["run_id"], "resume")
