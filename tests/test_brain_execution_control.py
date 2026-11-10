from threading import Event
from time import monotonic

from app.services.brain.brain_executor import BrainExecutor
from app.services.brain.brain_state import BrainState
from app.services.brain.execution_control import BrainExecutionControl


class OneModuleRegistry:
    def __init__(self, module):
        self.module = module

    def get_modules(self):
        return [self.module]


def test_expired_deadline_stops_before_first_module():
    class Module:
        name = "conversation"
        order = 1

        def execute(self, state):
            raise AssertionError("expired execution must not enter a stage")

    control = BrainExecutionControl(
        execution_id="expired",
        session_id="session",
        deadline=monotonic() - 1,
        _cancel_event=Event(),
    )
    result = BrainExecutor(OneModuleRegistry(Module())).execute_with_trace(
        BrainState(user_input="test"),
        control=control,
    )
    assert result["state"].status == "timed_out"
    assert result["trace"][0]["status"] == "timed_out"


def test_cancelled_run_stops_before_first_module():
    class Module:
        name = "conversation"
        order = 1

        def execute(self, state):
            raise AssertionError("cancelled execution must not enter a stage")

    control = BrainExecutionControl(
        execution_id="cancelled",
        session_id="session",
        deadline=monotonic() + 60,
        _cancel_event=Event(),
    )
    control.cancel()
    result = BrainExecutor(OneModuleRegistry(Module())).execute_with_trace(
        BrainState(user_input="test"),
        control=control,
    )
    assert result["state"].status == "cancelled"


def test_non_retry_safe_module_is_not_retried():
    class FailingModule:
        name = "conversation"
        order = 1

        def __init__(self):
            self.attempts = 0

        def execute(self, state):
            self.attempts += 1
            raise RuntimeError("side effect may have happened")

    module = FailingModule()
    executor = BrainExecutor(OneModuleRegistry(module))
    state = BrainState(user_input="test")
    try:
        executor.execute_with_trace(state)
    except RuntimeError:
        pass
    else:
        raise AssertionError("failure must propagate")
    assert module.attempts == 1
    assert state.status == "failed"
    assert state.current_stage == ""


def test_retry_safe_module_uses_bounded_retry():
    class FlakyModule:
        name = "conversation"
        order = 1
        retry_safe = True

        def __init__(self):
            self.attempts = 0

        def execute(self, state):
            self.attempts += 1
            if self.attempts < 2:
                raise RuntimeError("temporary failure")
            return state

    module = FlakyModule()
    result = BrainExecutor(OneModuleRegistry(module)).execute_with_trace(
        BrainState(user_input="test")
    )
    assert module.attempts == 2
    assert result["state"].status == "completed"
    assert [item["status"] for item in result["trace"]] == ["failed", "completed"]


def test_cancellation_between_stages_stops_before_next_stage():
    calls = []

    class First:
        name = "first"
        order = 1

        def execute(self, state):
            calls.append("first")
            control.cancel()
            return state

    class Second:
        name = "second"
        order = 2

        def execute(self, state):
            calls.append("second")
            return state

    class Registry:
        def get_modules(self):
            return [First(), Second()]

    control = BrainExecutionControl(
        execution_id="between-stages",
        session_id="session",
        deadline=monotonic() + 60,
        _cancel_event=Event(),
    )
    result = BrainExecutor(Registry()).execute_with_trace(
        BrainState(user_input="test"),
        control=control,
    )
    assert calls == ["first"]
    assert result["state"].status == "cancelled"


def test_execution_control_registry_releases_session_index():
    from app.services.brain.execution_control import BrainExecutionControlRegistry

    execution_id = "registry-test-run"
    session_id = "registry-test-session"
    control = BrainExecutionControlRegistry.register(execution_id, session_id)
    assert BrainExecutionControlRegistry.active_count() >= 1
    assert BrainExecutionControlRegistry.cancel_for_session(session_id) == 1
    assert control._cancel_event.is_set()
    BrainExecutionControlRegistry.release(execution_id)
    assert BrainExecutionControlRegistry.cancel_for_session(session_id) == 0


def test_brain_cancel_route_requests_cancellation_for_session():
    from app.routes.brain import cancel_brain_execution
    from app.services.brain.execution_control import BrainExecutionControlRegistry

    execution_id = "route-cancel-test-run"
    session_id = "route-cancel-test-session"
    control = BrainExecutionControlRegistry.register(execution_id, session_id)
    try:
        result = cancel_brain_execution(session_id)
        assert result["success"] is True
        assert result["cancelled_executions"] == 1
        assert control._cancel_event.is_set()
    finally:
        BrainExecutionControlRegistry.release(execution_id)


def test_untraced_execute_uses_same_guarded_path_and_terminal_status():
    class Module:
        name = "conversation"
        order = 1

        def execute(self, state):
            return state

    result = BrainExecutor(OneModuleRegistry(Module())).execute(
        BrainState(user_input="plain execution")
    )
    assert result.status == "completed"
    assert result.last_completed_stage == "conversation"
    assert result.current_stage == ""


def test_resume_does_not_retry_non_idempotent_module():
    class FailingModule:
        name = "conversation"
        order = 1

        def __init__(self):
            self.attempts = 0

        def execute(self, state):
            self.attempts += 1
            raise RuntimeError("possibly committed side effect")

    module = FailingModule()
    executor = BrainExecutor(OneModuleRegistry(module))
    state = BrainState(user_input="resume")
    try:
        executor.resume(state, 1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("unsafe resume failure must propagate")
    assert module.attempts == 1
    assert state.status == "failed"
    assert state.current_stage == ""


def test_resume_rejects_boolean_stage_index():
    class Module:
        name = "conversation"
        order = 1

        def execute(self, state):
            return state

    executor = BrainExecutor(OneModuleRegistry(Module()))
    try:
        executor.resume(BrainState(user_input="resume"), True)
    except TypeError:
        pass
    else:
        raise AssertionError("boolean must not be accepted as a stage index")


def test_brain_service_persists_cancelled_pipeline_as_failure(monkeypatch):
    from app.services.brain.brain_service import BrainService
    from app.services.brain.brain_request import BrainRequest
    from app.services.history.event_logger_service import EventLoggerService
    from app.services.resources.resource_budget_service import ResourceBudgetService

    session = {
        "session_id": "cancelled-service-session",
        "active_project": None,
        "active_mode": None,
        "goal_id": None,
        "cognitive_state": None,
        "context_snapshots": [],
    }

    class Sessions:
        def resolve_session(self, **kwargs):
            return session

    class Memory:
        def retrieve_relevant(self, **kwargs):
            return {}

        def get_all(self):
            return {"goals": [], "decisions": [], "memory_links": []}

    class Pipeline:
        def execute_with_trace(self, state, control=None):
            assert control is not None
            state.status = "cancelled"
            state.current_stage = ""
            return {"state": state, "trace": [{"status": "cancelled"}]}

    service = BrainService.__new__(BrainService)
    service.sessions = Sessions()
    service.memory = Memory()
    state = BrainState(user_input="cancel me")
    state.execution_context.update(session_id=session["session_id"])
    service.create_state = lambda request: state
    service._restore_session_state = lambda state, session: None
    service._resolve_mode = lambda state: None
    service._record_command = lambda state: None
    service.validate = lambda state: {"valid": True}
    service.pipeline = Pipeline()
    recorded = []
    persisted = []
    service._record_pipeline = lambda **kwargs: recorded.append(kwargs)
    service._persist_run = lambda *args, **kwargs: persisted.append(kwargs)

    monkeypatch.setattr(EventLoggerService, "log", lambda self, **kwargs: None)
    monkeypatch.setattr(ResourceBudgetService, "execution_guidance", lambda self: {})

    response = service.execute(BrainRequest(message="cancel me", session_id=session["session_id"]))

    assert response.success is False
    assert response.state.status == "cancelled"
    assert recorded[-1]["success"] is False
    assert persisted[-1]["success"] is False
    from app.services.brain.execution_control import BrainExecutionControlRegistry
    assert BrainExecutionControlRegistry.active_count() == 0


def test_brain_cancel_endpoint_is_registered_in_fastapi():
    from fastapi.testclient import TestClient
    from app.main import app

    response = TestClient(app).post("/brain/cancel/non-active-session")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["cancelled_executions"] == 0
