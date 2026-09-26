from app.services.brain.brain_request import BrainRequest
from app.services.brain.brain_service import BrainService
from app.services.command_parser_service import CommandParserService
from app.services.modes.mode_manager_service import ModeManagerService


def test_brain_service_executes_pipeline():
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
