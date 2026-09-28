from app.agents.agent_manager import AgentManager
from app.main import app
from fastapi.testclient import TestClient
from app.agents.workflow_engine import WorkflowEngine
from app.services.workflow_recovery.run_recovery_service import RunRecoveryService
from pathlib import Path
import time


class SlowAgent:
    name = "slow_agent"
    capabilities = ["test"]

    def execute(self, task):
        time.sleep(2)
        return {"success": True}


class LargeResultAgent:
    name = "large_result_agent"
    capabilities = ["test"]

    def execute(self, task):
        return {"payload": "x" * 300000}


def test_agent_manager_routes_known_work_and_reports_provider_unavailable():
    manager = AgentManager()
    assert set(manager.list_agents()) == {"code_agent", "planner_agent", "research_agent"}

    planned = manager.dispatch("Plan the implementation steps for a project")
    assert planned["success"] is True
    assert planned["agent"] == "planner_agent"
    assert planned["retry_count"] == 0

    research = manager.dispatch("Research the current best database")
    assert research["success"] is False
    assert research["state"] == "unavailable"
    assert research["result"]["code"] == "provider_unavailable"


def test_agent_manager_rejects_unbounded_or_unroutable_tasks():
    manager = AgentManager()
    assert manager.dispatch("ordinary unknown request")["code"] == "no_matching_agent"
    assert manager.run("planner_agent", "x" * (manager.MAX_TASK_LENGTH + 1))["code"] == "task_too_large"
    assert manager.run("planner_agent", "  ")["code"] == "invalid_task"


def test_agent_manager_terminates_work_after_timeout():
    manager = AgentManager(timeout_seconds=0.2)
    manager.register(SlowAgent())
    result = manager.run("slow_agent", "wait")
    assert result["success"] is False
    assert result["state"] == "timed_out"
    assert result["code"] == "agent_timeout"


def test_agent_manager_drains_large_result_without_deadlock():
    manager = AgentManager(timeout_seconds=5)
    manager.register(LargeResultAgent())
    result = manager.run("large_result_agent", "return a large value")
    assert result["success"] is True
    assert len(result["result"]["payload"]) == 300000


def test_code_agent_runs_inside_orchestrator_and_returns_valid_project():
    result = AgentManager().run("code_agent", "Build an expense API with search")
    assert result["success"] is True
    source = result["result"]["files"]["main.py"]
    compile(source, "agent_generated_project.py", "exec")
    assert '"/expenses/search"' in source


def test_agents_api_exposes_real_dispatch_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    response = client.post("/agents/dispatch", json={"task": "Research a reliable source"})
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["result"]["code"] == "provider_unavailable"


def test_workflow_runs_ordered_project_pipeline_and_verifies_before_save(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = WorkflowEngine().execute("Build a FastAPI expense API with authentication")
    assert result["success"] is True
    assert [item["step"] for item in result["results"] if isinstance(item, dict) and "step" in item] == ["validate"]
    generated = result["context"]["code"]
    assert generated["validation"]["valid"] is True
    assert result["context"]["save_project"]["success"] is True
    saved = Path(result["context"]["save_project"]["saved_to"]) / "main.py"
    assert saved.is_file()
    assert "get_current_user" in saved.read_text(encoding="utf-8")


def test_workflow_stops_immediately_when_builder_refines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []

    class Planner:
        def execute(self, goal):
            return {"success": True, "steps": ["builder", "execute", "code", "save_project"]}

    class Router:
        def execute_step(self, step, goal, context):
            calls.append(step)
            return {"status": "refine", "success": False, "reason": "clarification required"}

    engine = WorkflowEngine.__new__(WorkflowEngine)
    engine.planner = Planner()
    engine.router = Router()
    engine.recovery = RunRecoveryService()
    engine.isolated = False

    result = engine.execute("Build an expense API")

    assert result["success"] is False
    assert result["failed_step"] == "builder"
    assert calls == ["builder"]
