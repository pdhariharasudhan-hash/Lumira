import json
from app.services.background_tasks.background_agent_task_service import BackgroundAgentTaskService

class FakeExecutor:
    def __init__(self, result=None):
        self.result = result or {"success": True, "state": "completed"}
        self.calls = []
    def execute(self, task, agent_name=None):
        self.calls.append((task, agent_name))
        return self.result

def test_background_agent_task_persists_queue_and_completion(tmp_path):
    executor = FakeExecutor()
    service = BackgroundAgentTaskService(tmp_path / "jobs.json", executor=executor)
    created = service.create("Plan a project", "planner_agent")
    task_id = created["task"]["task_id"]
    assert created["task"]["status"] == "queued"
    result = service.execute(task_id)
    assert result["success"] is True
    assert result["task"]["status"] == "completed"
    assert json.loads((tmp_path / "jobs.json").read_text())[0]["status"] == "completed"
    assert executor.calls == [("Plan a project", "planner_agent")]

def test_background_task_failure_is_persisted(tmp_path):
    service = BackgroundAgentTaskService(tmp_path / "jobs.json", executor=FakeExecutor({"success": False, "code": "provider_unavailable", "message": "No provider"}))
    task_id = service.create("Research a topic")["task"]["task_id"]
    result = service.execute(task_id)
    assert result["success"] is False
    assert result["task"]["status"] == "failed"
    assert result["task"]["error"] == "No provider"

def test_restart_marks_queued_and_running_jobs_interrupted(tmp_path):
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps([{"task_id": "queued", "status": "queued"}, {"task_id": "running", "status": "running"}, {"task_id": "done", "status": "completed"}]))
    service = BackgroundAgentTaskService(path)
    items = service.list()["tasks"]
    assert [item["status"] for item in items] == ["interrupted", "interrupted", "completed"]
    assert service.get("queued")["error"]

def test_background_task_rejects_invalid_task_and_agent(tmp_path):
    service = BackgroundAgentTaskService(tmp_path / "jobs.json")
    assert service.create("   ")["code"] == "invalid_task"
    assert service.create("do work", "unregistered")["code"] == "invalid_agent"
    assert service.list()["count"] == 0


def test_background_task_api_queues_and_persists_completion(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.routes.background_tasks as route

    executor = FakeExecutor()
    monkeypatch.setattr(route, "service", BackgroundAgentTaskService(tmp_path / "api_jobs.json", executor=executor))
    client = TestClient(app)

    response = client.post("/background-tasks", json={"task": "Plan a bounded project", "agent_name": "planner_agent"})
    assert response.status_code == 202
    task_id = response.json()["task"]["task_id"]
    detail = client.get(f"/background-tasks/{task_id}")
    assert detail.status_code == 200
    assert detail.json()["task"]["status"] == "completed"
    assert executor.calls == [("Plan a bounded project", "planner_agent")]


def test_background_task_api_rejects_unknown_agent(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.routes.background_tasks as route

    monkeypatch.setattr(route, "service", BackgroundAgentTaskService(tmp_path / "api_jobs.json", executor=FakeExecutor()))
    response = TestClient(app).post("/background-tasks", json={"task": "Do work", "agent_name": "shell_agent"})
    assert response.status_code == 422


def test_autonomous_background_task_requires_explicit_permission(tmp_path, monkeypatch):
    from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
    monkeypatch.chdir(tmp_path)
    service = BackgroundAgentTaskService(tmp_path / "jobs.json", executor=FakeExecutor())
    result = service.create("Run an autonomous research step", autonomous=True)
    assert result["success"] is False
    assert result["code"] == "autonomous_permission_required"

    permissions = AutonomyPermissionService(tmp_path / "autonomy.json")
    permissions.set_permission("agent.dispatch", True, "bounded test")
    service = BackgroundAgentTaskService(
        tmp_path / "jobs-authorized.json",
        executor=FakeExecutor(),
        autonomy_service=permissions,
    )
    created = service.create("Run an autonomous research step", autonomous=True)
    assert created["success"] is True
    assert created["task"]["autonomous"] is True


def test_background_agent_task_redacts_secret_fields_before_persistence(tmp_path):
    executor = FakeExecutor({"success": True, "api_key": "super-secret-token"})
    service = BackgroundAgentTaskService(tmp_path / "jobs.json", executor=executor)
    task_id = service.create("Run a safe task")["task"]["task_id"]

    result = service.execute(task_id)

    assert result["success"] is True
    assert "super-secret-token" not in result["task"]["result"]
    assert "[REDACTED]" in result["task"]["result"]
