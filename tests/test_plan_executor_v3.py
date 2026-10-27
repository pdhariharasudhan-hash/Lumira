from app.services.planner import plan_executor_v3 as module


class FakeBuilder:
    calls = 0
    result = {"status": "accept", "suggested_steps": [{"id": "step_1"}]}

    def build(self, goal):
        type(self).calls += 1
        return type(self).result


class FakeExecute:
    calls = 0
    result = {"status": "accept", "execution_order": ["step_1"], "task_steps": ["step_1"]}

    def execute(self, goal, builder):
        type(self).calls += 1
        return type(self).result


class FakeCode:
    calls = 0
    result = {"status": "accept", "files": {"main.py": "pass"}}

    def generate(self, goal, execution):
        type(self).calls += 1
        return type(self).result


class FakeSession:
    calls = 0
    result = {"session_id": "test-session"}

    def create_session(self, goal, builder, execution, code):
        type(self).calls += 1
        return type(self).result


def setup_fakes(monkeypatch):
    for cls in (FakeBuilder, FakeExecute, FakeCode, FakeSession):
        cls.calls = 0
    FakeBuilder.result = {"status": "accept", "suggested_steps": [{"id": "step_1"}]}
    FakeExecute.result = {"status": "accept", "execution_order": ["step_1"], "task_steps": ["step_1"]}
    FakeCode.result = {"status": "accept", "files": {"main.py": "pass"}}
    FakeSession.result = {"session_id": "test-session"}
    monkeypatch.setattr(module, "BuilderService", FakeBuilder)
    monkeypatch.setattr(module, "ExecuteService", FakeExecute)
    monkeypatch.setattr(module, "CodeService", FakeCode)
    monkeypatch.setattr(module, "ExecutionSessionService", FakeSession)


def test_plan_executor_v3_stops_after_builder_rejects(monkeypatch):
    setup_fakes(monkeypatch)
    FakeBuilder.result = {"status": "refine", "reasons": ["goal unclear"]}

    result = module.PlanExecutorV3().execute("build an API")

    assert result["success"] is False
    assert result["state"] == "blocked"
    assert result["code"] == "builder_rejected"
    assert FakeExecute.calls == 0
    assert FakeCode.calls == 0
    assert FakeSession.calls == 0


def test_plan_executor_v3_stops_after_execution_plan_rejects(monkeypatch):
    setup_fakes(monkeypatch)
    FakeExecute.result = {"status": "refine", "blockers": ["missing steps"]}

    result = module.PlanExecutorV3().execute("build an API")

    assert result["success"] is False
    assert result["code"] == "plan_rejected"
    assert FakeCode.calls == 0
    assert FakeSession.calls == 0


def test_plan_executor_v3_stops_after_code_generation_rejects(monkeypatch):
    setup_fakes(monkeypatch)
    FakeCode.result = {"status": "reject", "error": "invalid generated plan"}

    result = module.PlanExecutorV3().execute("build an API")

    assert result["success"] is False
    assert result["code"] == "code_generation_rejected"
    assert FakeSession.calls == 0


def test_plan_executor_v3_requires_session_persistence(monkeypatch):
    setup_fakes(monkeypatch)
    FakeSession.result = {"success": False, "error": "persistence failed"}

    result = module.PlanExecutorV3().execute("build an API")

    assert result["success"] is False
    assert result["code"] == "session_persistence_failed"


def test_plan_executor_v3_reports_planning_only_not_code_execution(monkeypatch):
    setup_fakes(monkeypatch)

    result = module.PlanExecutorV3().execute("  build an API  ")

    assert result["success"] is True
    assert result["state"] == "completed"
    assert result["goal"] == "build an API"
    assert result["execution_mode"] == "planning_only"
    assert result["last_completed_stage"] == "session"
    assert FakeBuilder.calls == FakeExecute.calls == FakeCode.calls == FakeSession.calls == 1


def test_plan_executor_v3_rejects_invalid_goal_before_work(monkeypatch):
    setup_fakes(monkeypatch)

    result = module.PlanExecutorV3().execute(" " * 5)

    assert result["success"] is False
    assert result["code"] == "invalid_goal"
    assert FakeBuilder.calls == 0
