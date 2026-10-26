from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.command_parser_service import CommandParserService
from app.routes.command import _command_result_success


def test_command_result_does_not_treat_non_object_as_success():
    assert _command_result_success(None) is False
    assert _command_result_success("unexpected") is False
    assert _command_result_success({"success": False}) is False
    assert _command_result_success({"success": "false"}) is False
    assert _command_result_success({"success": 1}) is False
    assert _command_result_success({"status": ["completed"], "success": True}) is False
    assert _command_result_success({"state": "", "success": True}) is False
    assert _command_result_success({"status": "running", "success": True}) is False
    assert _command_result_success({"state": "pending"}) is False
    assert _command_result_success({"status": "completed"}) is True
    assert _command_result_success({"status": "failed"}) is False
    assert _command_result_success({"state": "blocked"}) is False
    assert _command_result_success({"status": "FAILED"}) is False
    assert _command_result_success({"status": "cancelled"}) is False
    assert _command_result_success({"state": "error"}) is False
    assert _command_result_success({"status": "planned"}) is True
    assert _command_result_success({"success": True, "status": "failed"}) is False
    assert _command_result_success({"success": True, "state": "rejected"}) is False


def test_command_parser_requires_explicit_agent_delegation():
    parser = CommandParserService()
    generic = parser.parse("delegate to agent: Research ESP32 sensor options")
    named = parser.parse("delegate to code_agent: Create a small API")

    assert generic == {
        "success": True,
        "capability": "agent_task",
        "payload": {"task": "Research ESP32 sensor options", "agent_name": None},
    }
    assert named == {
        "success": True,
        "capability": "agent_task",
        "payload": {"task": "Create a small API", "agent_name": "code_agent"},
    }
    assert parser.parse("delegate to agent: ")["success"] is False
    assert parser.parse("research ESP32 sensor options").get("capability") != "agent_task"


def test_primary_command_passes_existing_brain_result_to_agent_orchestrator(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain_response = SimpleNamespace(
        success=True,
        error=None,
        state=SimpleNamespace(
            mode=SimpleNamespace(active_mode="personal"),
            execution_context=SimpleNamespace(execution_id="brain-command-test"),
            last_completed_stage="learning",
        ),
        trace=[],
    )
    brain_calls = []

    class FakeBrainService:
        def execute(self, request):
            brain_calls.append(request)
            return brain_response

    orchestrator_calls = []

    class FakeOrchestrator:
        def validate_request(self, task, agent_name=None):
            return None

        def execute_after_brain(self, task, response, agent_name=None):
            orchestrator_calls.append((task, response, agent_name))
            return {
                "success": True,
                "state": "completed",
                "agent": agent_name or "research_agent",
                "orchestration": {"brain_gate": "passed"},
            }

    monkeypatch.setattr("app.routes.command.BrainService", FakeBrainService)
    monkeypatch.setattr("app.routes.command.BrainAgentOrchestrator", FakeOrchestrator)

    response = TestClient(app).post(
        "/command",
        json={"input": "delegate to research_agent: Research safe ESP32 power options"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["result"]["orchestration"]["brain_gate"] == "passed"
    assert len(brain_calls) == 1
    assert orchestrator_calls == [
        ("Research safe ESP32 power options", brain_response, "research_agent")
    ]



def test_oversized_agent_task_is_rejected_before_main_brain_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain_calls = []

    class FakeBrainService:
        def execute(self, request):
            brain_calls.append(request)
            raise AssertionError("oversized agent task must be rejected before brain execution")

    class FakeOrchestrator:
        def validate_request(self, task, agent_name=None):
            if len(task) > 10000:
                return {
                    "success": False,
                    "state": "rejected",
                    "code": "task_too_large",
                    "message": "Agent tasks are limited to 10000 characters.",
                }
            return None

        def execute_after_brain(self, task, response, agent_name=None):
            raise AssertionError("rejected task must not reach agent dispatch")

    monkeypatch.setattr("app.routes.command.BrainService", FakeBrainService)
    monkeypatch.setattr("app.routes.command.BrainAgentOrchestrator", FakeOrchestrator)

    task = "x" * 10001
    response = TestClient(app).post(
        "/command",
        json={"input": f"delegate to agent: {task}"},
    )

    # GenericInput enforces the same 10,000-character limit before route logic,
    # so an oversized request must be rejected by request validation without
    # starting the main brain or an agent.
    assert response.status_code == 422
    assert brain_calls == []


def test_primary_command_rejects_non_boolean_brain_success_before_agent_dispatch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain_response = SimpleNamespace(
        success="false",
        error="malformed success flag",
        state=SimpleNamespace(
            mode=SimpleNamespace(active_mode="personal"),
            execution_context=SimpleNamespace(execution_id="brain-command-invalid"),
            last_completed_stage="validation",
        ),
        trace=[],
    )

    class FakeBrainService:
        def execute(self, request):
            return brain_response

    class FakeOrchestrator:
        def validate_request(self, task, agent_name=None):
            return None

        def execute_after_brain(self, task, response, agent_name=None):
            raise AssertionError("invalid brain success must not reach agent dispatch")

    monkeypatch.setattr("app.routes.command.BrainService", FakeBrainService)
    monkeypatch.setattr("app.routes.command.BrainAgentOrchestrator", FakeOrchestrator)

    response = TestClient(app).post(
        "/command",
        json={"input": "delegate to research_agent: Research safe ESP32 power options"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
