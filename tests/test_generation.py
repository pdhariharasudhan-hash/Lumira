from app.services.brain.brain_request import BrainRequest
from app.services.brain.brain_service import BrainService
from app.services.code.code_service import CodeService
from app.services.projects.project_writer import ProjectWriter
from app.services.brain.brain_executor import BrainExecutor
from app.services.brain.brain_state import BrainState
from app.services.image.image_generation_service import ImageGenerationService


def test_end_to_end_project_request_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = BrainService()
    response = service.execute(BrainRequest(message="Build a simple task management API with authentication"))
    assert response.success is True
    state = response.state
    assert state.goal.primary_goal
    assert state.objective.primary_objective
    assert state.context.project_type in {"api", "application", "general"}
    assert state.plan is not None or state.planner.execution_steps or state.decision.next_action


def test_expense_api_name_ignores_framework_and_feature_terms():
    generated = CodeService().generate(
        "Build a FastAPI expense API with authentication",
        {},
    )

    assert generated["code_target"] == "expense_api"
    source = generated["files"]["main.py"]
    assert "hashlib.pbkdf2_hmac" in source
    assert "hmac.compare_digest" in source
    assert "Depends(get_current_user)" in source
    compile(source, "generated_expense_api.py", "exec")


def test_project_writer_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    try:
        ProjectWriter().save("../outside", {"main.py": "pass"}, {})
    except ValueError as error:
        assert "project_name" in str(error)
    else:
        raise AssertionError("unsafe project name was accepted")

    try:
        ProjectWriter().save("expense_api", {"../outside.py": "pass"}, {})
    except ValueError as error:
        assert "filenames" in str(error)
    else:
        raise AssertionError("unsafe generated filename was accepted")


def test_image_generation_requires_a_configured_provider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = ImageGenerationService().generate("an expense dashboard")

    assert result["success"] is False
    assert result["code"] == "provider_unavailable"
    assert not list((tmp_path / "artifacts" / "images").glob("*.txt"))


def test_brain_executor_recovers_and_retries_failed_stage():
    class FlakyConversation:
        name = "conversation"
        order = 1

        def __init__(self):
            self.attempts = 0

        def execute(self, state):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("controlled failure")
            return state

    class Registry:
        def __init__(self, module):
            self.module = module

        def get_modules(self):
            return [self.module]

    module = FlakyConversation()
    executor = BrainExecutor(registry=Registry(module))
    result = executor.execute_with_trace(BrainState(user_input="test recovery"))

    assert result["state"].user_input == "test recovery"
    assert [entry["status"] for entry in result["trace"]] == ["failed", "completed"]
    assert result["trace"][1]["recovery_status"] == "recovered"
    recovery = executor.get_recovery_state()
    assert recovery.failures[0].error == "controlled failure"
    assert recovery.failures[0].retry_count == 0
    assert recovery.failures[0].recovered is True
