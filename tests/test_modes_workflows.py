from fastapi.testclient import TestClient

from app.main import app
from app.services.capabilities.capability_router_service import CapabilityRouterService
from app.services.command_parser_service import CommandParserService
from app.services.modes.mode_detection_service import ModeDetectionService
from app.services.search.unified_search_service import UnifiedSearchService


def test_business_command_creates_goal_workflow_artifact_and_session_links(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).post(
        "/command",
        json={"input": "Plan for launching my PCB design service."},
    )

    assert response.status_code == 200
    body = response.json()
    result = body["result"]
    assert result["success"] is True
    assert result["plan"]["metrics"] == {"data_available": False, "values": {}}
    assert result["plan"]["evidence_needed"]
    assert result["workflow"]["category"] == "business"
    assert result["workflow"]["status"] == "planned"
    assert result["goal"]["goal_id"] == body["context"]["goal_id"]
    assert result["artifact"]["artifact_id"] in body["context"]["recent_artifact_ids"]
    assert result["workflow"]["workflow_id"] in body["context"]["recent_workflow_ids"]


def test_operations_workflow_persists_status_and_enforces_dependencies(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).post(
        "/command",
        json={"input": "Prepare today's Lumira development tasks."},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    workflow = result["workflow"]
    assert result["success"] is True
    assert workflow["category"] == "operations"
    assert len(workflow["tasks"]) >= 3

    client = TestClient(app)
    workflow_id = workflow["workflow_id"]
    first, second = workflow["tasks"][:2]
    blocked = client.patch(
        f"/workflows/{workflow_id}/tasks/{second['task_id']}",
        json={"status": "in_progress"},
    )
    assert blocked.status_code == 422
    rejected_completion = client.patch(
        f"/workflows/{workflow_id}/tasks/{second['task_id']}",
        json={"status": "completed", "result": "done"},
    )
    assert rejected_completion.status_code == 422

    assert client.patch(
        f"/workflows/{workflow_id}/tasks/{first['task_id']}",
        json={"status": "in_progress"},
    ).status_code == 200
    completed = client.patch(
        f"/workflows/{workflow_id}/tasks/{first['task_id']}",
        json={"status": "completed", "result": "verified"},
    )
    assert completed.status_code == 200
    refreshed = client.get(f"/workflows/{workflow_id}").json()
    assert refreshed["tasks"][0]["status"] == "completed"
    assert refreshed["status"] == "in_progress"


def test_work_item_store_rejects_unhashable_persisted_statuses(tmp_path):
    import json
    import pytest
    from app.services.persistence.atomic_json_store import PersistenceIntegrityError
    from app.services.work_items.work_item_service import WorkItemService

    path = tmp_path / "work_items.json"
    service = WorkItemService(path)
    workflow = service.create_workflow(
        "operations", "Check persisted data", "Verify workflow status validation", ["Inspect data"]
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    document["workflows"][0]["status"] = ["planned"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="invalid status"):
        service.list_workflows()

    document["workflows"][0]["status"] = "planned"
    document["workflows"][0]["tasks"][0]["status"] = ["pending"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="invalid task status"):
        service.list_workflows()


def test_creator_payload_is_saved_as_a_searchable_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    parsed = CommandParserService().parse("Create a presentation about PCB design services")
    assert parsed["capability"] == "presentations"
    result = CapabilityRouterService().execute(parsed["capability"], parsed["payload"])
    assert result["success"] is True
    assert result["artifact"]["type"] == "exports"
    indexed = UnifiedSearchService().search_all("PCB design services")
    assert any("artifact_id" in item for item in indexed["artifacts"])
    assert result["creator_output"]["status"] == "artifact_created"
    assert result["creator_artifact"]["type"] == "exports"


def test_generator_command_creates_a_searchable_architecture_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    parsed = CommandParserService().parse("Generate an architecture diagram for a secure expense API")
    assert parsed["capability"] == "architecture_diagrams"
    result = CapabilityRouterService().execute(parsed["capability"], parsed["payload"])
    assert result["success"] is True
    assert result["artifact"]["type"] == "diagrams"
    indexed = UnifiedSearchService().search_all("secure expense API")
    assert any("artifact_id" in item for item in indexed["artifacts"])


def test_auto_mode_detection_distinguishes_business_operations_creator_and_generator():
    detector = ModeDetectionService()
    expected = {
        "Plan for launching my PCB design service": "business",
        "Prepare today's Lumira development tasks": "operations",
        "Create a presentation for the product launch": "creator",
        "Generate a flowchart for user onboarding": "generator",
    }
    for request, mode in expected.items():
        assert detector.detect(request).selected_mode == mode


def test_unconfigured_email_automation_returns_a_plan_without_claiming_delivery():
    result = CapabilityRouterService().execute("email_automation", {"request": "Send the weekly report"})
    assert result["success"] is True
    assert result["status"] == "planned"
    assert result["execution_started"] is False
    assert "no schedule" in result["execution_boundary"]
