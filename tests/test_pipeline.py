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


def test_command_parser_resolves_short_continue_phrases_to_project_resume():
    parser = CommandParserService()
    for command in (
        "continue",
        "Continue where we stopped",
        "continue where we left off",
        "continue my project",
        "resume my project",
        "resume the project",
    ):
        parsed = parser.parse(command)
        assert parsed["success"] is True, command
        assert parsed["capability"] == "resume_project", command
        assert parsed["payload"] == {}, command


def test_command_parser_supports_bounded_tamil_and_tanglish_commands():
    parser = CommandParserService()

    for command in (
        "தேடு Raspberry Pi 5",
        "தேடுங்கள் Raspberry Pi 5",
        "thedu Raspberry Pi 5",
        "search pannu Raspberry Pi 5",
    ):
        parsed = parser.parse(command)
        assert parsed["success"] is True, command
        assert parsed["capability"] == "search", command
        assert parsed["payload"]["query"] == "Raspberry Pi 5", command

    for command in ("தொடரு", "தொடர்ந்து செய்", "மீண்டும் தொடரு", "continue pannu"):
        parsed = parser.parse(command)
        assert parsed["success"] is True, command
        assert parsed["capability"] == "resume_project", command

    for command in (
        "ஒரு செயலி உருவாக்கு",
        "oru website create pannu",
        "oru app build pannunga",
    ):
        parsed = parser.parse(command)
        assert parsed["success"] is True, command
        assert parsed["capability"] == "project_generation", command
        assert parsed["payload"]["idea"] == command

    assert parser.parse("அம்சங்கள் காட்டு")["capability"] == "list_features"


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
        retry_safe = True

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


def test_intent_classifier_uses_supported_tamil_and_tanglish_commands():
    from app.services.language.intent_classifier_service import IntentClassifierService

    classifier = IntentClassifierService()
    assert classifier.classify("தேடுங்கள் Raspberry Pi 5") == "search"
    assert classifier.classify("oru app build pannunga") == "build"
    assert classifier.classify("அம்சங்கள் காட்டு") == "show"
    assert classifier.classify("தொடரு") == "continue"
    assert classifier.classify("research this sensor") == "research"
    assert classifier.classify(None) == "chat"


def test_language_detection_recognizes_bounded_tanglish_lexicon():
    from app.services.language.language_detection_service import LanguageDetectionService

    detector = LanguageDetectionService()
    assert detector.detect("search pannu Raspberry Pi 5")["language"] == "ta-en"
    assert detector.detect("epdi iruka")["language"] == "ta"
    assert detector.detect("oru app create pannu")["language"] == "ta-en"


def test_pipeline_history_accepts_execution_without_active_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    history = PipelineHistoryService()
    record = history.record(
        execution_id="execution-without-project",
        request_id="request-without-project",
        session_id="session-without-project",
        project_id="",
        user_input="Explain a Python concept",
        success=True,
        trace=[{"module": "conversation", "status": "completed"}],
    )

    assert record["project_id"] == ""
    assert history.get_by_execution_id("execution-without-project")["project_id"] == ""
    assert history.get_by_project_id("") == []
