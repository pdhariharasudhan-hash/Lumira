from fastapi.testclient import TestClient

from app.main import app
from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
from app.services.brain.brain_agent_orchestrator import BrainAgentOrchestrator


def test_autonomy_permissions_fail_closed_and_persist_state(tmp_path):
    service = AutonomyPermissionService(tmp_path / "permissions.json")

    denied = service.authorize("workflow.run", autonomous=True)
    assert denied["allowed"] is False
    assert denied["code"] == "autonomous_permission_required"
    assert service.authorize("workflow.run", autonomous=False)["allowed"] is True

    service.set_permission("workflow.run", True, "approved for a bounded test")
    allowed = service.authorize("workflow.run", autonomous=True)
    assert allowed["allowed"] is True

    service.record_state("workflow.run", "started", run_id="run-1")
    reloaded = AutonomyPermissionService(tmp_path / "permissions.json")
    status = reloaded.status()
    assert status["permissions"]["workflow.run"]["enabled"] is True
    assert status["recent_events"][-1]["state"] == "started"


def test_autonomy_permission_rejects_unknown_operation(tmp_path):
    service = AutonomyPermissionService(tmp_path / "permissions.json")
    try:
        service.authorize("unknown", autonomous=True)
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("unknown autonomous operation must be rejected")


def test_autonomy_routes_expose_and_update_explicit_permission(monkeypatch, tmp_path):
    import app.routes.autonomy as route

    service = AutonomyPermissionService(tmp_path / "permissions.json")
    monkeypatch.setattr(route, "service", service)
    client = TestClient(app)

    response = client.put(
        "/autonomy/permissions/workflow.run",
        json={"enabled": True, "reason": "bounded workflow approval"},
    )
    assert response.status_code == 200
    assert response.json()["permission"]["enabled"] is True

    response = client.get("/autonomy/permissions")
    assert response.status_code == 200
    assert response.json()["permissions"]["workflow.run"]["enabled"] is True


def test_autonomous_agent_dispatch_is_blocked_without_permission(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = BrainAgentOrchestrator().execute("Research a bounded question", autonomous=True)
    assert result["success"] is False
    assert result["code"] == "autonomous_permission_required"


def test_autonomous_workflow_is_denied_before_task_mutation(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from app.routes import workflows as workflow_route
    from app.services.work_items.work_item_service import WorkItemService

    workflow = WorkItemService().create_workflow(
        category="operations",
        title="Bounded autonomous run",
        request="Run one approved step",
        tasks=["Approved step"],
    )
    permission_service = AutonomyPermissionService(tmp_path / "permissions.json")
    monkeypatch.setattr(workflow_route, "AutonomyPermissionService", lambda: permission_service)

    result = workflow_route.run_ready_workflow_tasks(
        workflow["workflow_id"],
        workflow_route.WorkflowAgentRunRequest(autonomous=True),
    )

    assert result["success"] is False
    assert result["stop_reason"] == "autonomous_permission_required"
    assert result["executed_count"] == 0
    assert WorkItemService().get_workflow(workflow["workflow_id"])["tasks"][0]["status"] == "pending"
