from types import SimpleNamespace

from app.services.brain.brain_agent_orchestrator import BrainAgentOrchestrator


class FakeBrain:
    def __init__(self, success=True):
        self.success = success
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        if not self.success:
            return SimpleNamespace(success=False, error="controlled validation failure")
        return SimpleNamespace(
            success=True,
            error=None,
            state=SimpleNamespace(
                execution_context=SimpleNamespace(execution_id="exec-test"),
                last_completed_stage="learning",
            ),
        )


class FakeAgents:
    def __init__(self):
        self.calls = []

    def dispatch(self, task):
        self.calls.append(("dispatch", task))
        return {"success": True, "state": "planned", "agent": "planner_agent", "result": {"status": "planned"}}

    def run(self, agent_name, task):
        self.calls.append((agent_name, task))
        return {"success": True, "state": "completed", "agent": agent_name, "result": {"status": "completed"}}


def test_agent_dispatch_passes_through_main_brain_before_dispatch(monkeypatch):
    from app.services.resources.resource_budget_service import ResourceBudgetService
    monkeypatch.setattr(ResourceBudgetService, "snapshot", lambda self: {"resource_pressure": "normal"})
    from threading import Lock
    monkeypatch.setattr(BrainAgentOrchestrator, "_dispatch_lock", Lock())
    brain = FakeBrain()
    agents = FakeAgents()
    agents.dispatch = lambda task: (agents.calls.append(("dispatch", task)) or {"success": True, "state": "started", "agent": "planner_agent", "result": {"status": "started"}})

    result = BrainAgentOrchestrator(brain, agents).execute("Plan my project")

    assert brain.calls[0].message == "Plan my project"
    assert agents.calls == [("dispatch", "Plan my project")]
    assert result["success"] is True
    assert result["orchestration"] == {
        "brain_gate": "passed",
        "brain_execution_id": "exec-test",
        "brain_last_completed_stage": "learning",
        "agent_execution_started": True,
    }


def test_agent_is_not_started_when_main_brain_fails():
    brain = FakeBrain(success=False)
    agents = FakeAgents()

    result = BrainAgentOrchestrator(brain, agents).execute("Build a project")

    assert result["success"] is False
    assert result["code"] == "brain_validation_failed"
    assert agents.calls == []


def test_named_agent_execution_is_explicit_and_brain_gated():
    brain = FakeBrain()
    agents = FakeAgents()

    result = BrainAgentOrchestrator(brain, agents).execute("Generate code", "code_agent")

    assert agents.calls == [("code_agent", "Generate code")]
    assert result["agent"] == "code_agent"
    assert result["orchestration"]["brain_gate"] == "passed"


def test_invalid_named_agent_is_rejected_before_brain_side_effects():
    class Registry:
        def exists(self, name):
            return name == "known_agent"

    class Agents(FakeAgents):
        MAX_TASK_LENGTH = 10
        registry = Registry()

    brain = FakeBrain()
    agents = Agents()
    result = BrainAgentOrchestrator(brain, agents).execute("do it", "missing_agent")

    assert result["code"] == "agent_not_found"
    assert brain.calls == []
    assert agents.calls == []


def test_oversized_task_is_rejected_before_brain_side_effects():
    class Agents(FakeAgents):
        MAX_TASK_LENGTH = 10

    brain = FakeBrain()
    result = BrainAgentOrchestrator(brain, Agents()).execute("x" * 11)

    assert result["code"] == "task_too_large"
    assert brain.calls == []


def test_existing_brain_result_does_not_construct_a_second_brain(monkeypatch):
    def unexpected_brain_construction():
        raise AssertionError("execute_after_brain must reuse the caller's brain result")

    monkeypatch.setattr(
        "app.services.brain.brain_agent_orchestrator.BrainService",
        unexpected_brain_construction,
    )
    agents = FakeAgents()
    brain_response = SimpleNamespace(
        success=True,
        error=None,
        state=SimpleNamespace(
            execution_context=SimpleNamespace(execution_id="existing-exec"),
            last_completed_stage="learning",
        ),
    )

    result = BrainAgentOrchestrator(agent_manager=agents).execute_after_brain(
        "Research safe battery options",
        brain_response,
    )

    assert result["success"] is True
    assert agents.calls == [("dispatch", "Research safe battery options")]
    assert result["orchestration"]["brain_execution_id"] == "existing-exec"


def test_invalid_agent_manager_result_fails_closed():
    class InvalidAgents:
        def dispatch(self, task):
            return None

    brain_response = SimpleNamespace(
        success=True,
        state=SimpleNamespace(
            execution_context=SimpleNamespace(execution_id="exec-test"),
            last_completed_stage="learning",
        ),
    )

    result = BrainAgentOrchestrator(agent_manager=InvalidAgents()).execute_after_brain(
        "Run a bounded task",
        brain_response,
    )

    assert result["success"] is False
    assert result["code"] == "invalid_agent_result"
    assert "orchestration" not in result


def test_agent_dispatch_exception_returns_sanitized_failure():
    class BrokenAgents:
        def dispatch(self, task):
            raise RuntimeError("private implementation detail")

    brain_response = SimpleNamespace(
        success=True,
        state=SimpleNamespace(
            execution_context=SimpleNamespace(execution_id="exec-test"),
            last_completed_stage="learning",
        ),
    )

    result = BrainAgentOrchestrator(agent_manager=BrokenAgents()).execute_after_brain(
        "Run a bounded task",
        brain_response,
    )

    assert result["success"] is False
    assert result["code"] == "agent_dispatch_failed"
    assert result["message"] == "The agent manager failed before returning a valid result."
    assert "private implementation detail" not in str(result)


def test_rejected_dispatch_reports_that_agent_execution_never_started():
    class RejectingAgents:
        def dispatch(self, task):
            return {
                "success": False,
                "state": "rejected",
                "code": "no_matching_agent",
                "message": "No registered agent capability matches this task.",
            }

    brain_response = SimpleNamespace(
        success=True,
        state=SimpleNamespace(
            execution_context=SimpleNamespace(execution_id="exec-test"),
            last_completed_stage="learning",
        ),
    )

    result = BrainAgentOrchestrator(agent_manager=RejectingAgents()).execute_after_brain(
        "Do something unsupported",
        brain_response,
    )

    assert result["success"] is False
    assert result["orchestration"]["agent_execution_started"] is False


def test_missing_agent_state_does_not_claim_execution_started():
    class MalformedAgents:
        def dispatch(self, task):
            return {"success": False, "code": "malformed_result"}

    brain_response = SimpleNamespace(
        success=True,
        state=SimpleNamespace(
            execution_context=SimpleNamespace(execution_id="exec-test"),
            last_completed_stage="learning",
        ),
    )

    result = BrainAgentOrchestrator(agent_manager=MalformedAgents()).execute_after_brain(
        "Run a bounded task",
        brain_response,
    )

    assert result["success"] is False
    assert result["orchestration"]["agent_execution_started"] is False


def test_non_boolean_brain_success_never_authorizes_agent_execution():
    agents = FakeAgents()
    brain_response = SimpleNamespace(
        success="false",
        error="malformed brain response",
        state=SimpleNamespace(
            execution_context=SimpleNamespace(execution_id="exec-test"),
            last_completed_stage="learning",
        ),
    )

    result = BrainAgentOrchestrator(agent_manager=agents).execute_after_brain(
        "Run a bounded task",
        brain_response,
    )

    assert result["success"] is False
    assert result["code"] == "brain_validation_failed"
    assert agents.calls == []



def test_failed_agent_state_does_not_claim_execution_started():
    class FailedAgents:
        def dispatch(self, task):
            return {
                "success": False,
                "state": "failed",
                "code": "agent_process_failed",
            }

    brain_response = SimpleNamespace(
        success=True,
        state=SimpleNamespace(
            execution_context=SimpleNamespace(execution_id="exec-test"),
            last_completed_stage="learning",
        ),
    )

    result = BrainAgentOrchestrator(agent_manager=FailedAgents()).execute_after_brain(
        "Run a bounded task",
        brain_response,
    )

    assert result["success"] is False
    assert result["orchestration"]["agent_execution_started"] is False
