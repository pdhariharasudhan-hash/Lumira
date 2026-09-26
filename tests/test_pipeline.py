from app.services.brain.brain_request import BrainRequest
from app.services.brain.brain_service import BrainService
from app.services.command_parser_service import CommandParserService
from app.services.modes.mode_manager_service import ModeManagerService
from app.services.conversation.conversation_service import ConversationService
from app.services.conversation.conversation_models import ConversationState
from app.services.conversation.conversation_module import ConversationModule
from app.services.history.pipeline_history_service import PipelineHistoryService


def test_brain_service_executes_pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = BrainService()
    request = BrainRequest(message="Build a FastAPI expense API with authentication")
    response = service.execute(request)
    assert response.success is True
    assert response.state is not None
    assert response.state.user_input == request.message
    assert response.state.goal.primary_goal
    assert response.state.objective.primary_objective


def test_command_parser_handles_builder_request():
    parsed = CommandParserService().parse("Build a FastAPI expense API with authentication")
    assert parsed["success"] is True
    assert parsed["capability"] in {"project_engineering", "project_generation", "planning"}


def test_mode_manager_switches_modes():
    manager = ModeManagerService()
    manager.select("builder")
    assert manager.get_active_mode_id() == "builder"
    manager.switch("research")
    assert manager.get_active_mode_id() == "research"


def test_conversation_uses_intent_and_tamil_english_detection():
    state = ConversationService().analyze(
        "Build an API, தயவு செய்து",
        ConversationState(),
    )

    assert state.detected_intent == "build"
    assert state.detected_language == "ta-en"
    assert state.confidence == 1.0


def test_brain_retry_continues_through_learning_and_records_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = BrainService()
    conversation = ConversationModule()

    class FlakyConversation:
        name = "conversation"
        order = 1

        def __init__(self):
            self.attempts = 0

        def execute(self, state):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("controlled integration failure")
            return conversation.execute(state)

    service.registry._modules[0] = FlakyConversation()
    response = service.execute(
        BrainRequest(message="Build a FastAPI expense API")
    )

    assert response.success is True
    assert response.trace[0]["status"] == "failed"
    assert response.trace[1]["recovery_status"] == "recovered"
    assert [entry["module"] for entry in response.trace][-3:] == [
        "verification",
        "reflection",
        "learning",
    ]
    record = PipelineHistoryService().get_by_execution_id(
        response.state.execution_context.execution_id
    )
    assert record["success"] is True
    assert record["trace"] == response.trace
