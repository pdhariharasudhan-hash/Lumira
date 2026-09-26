from app.services.brain.brain_request import BrainRequest
from app.services.brain.brain_service import BrainService


def test_end_to_end_project_request_flow():
    service = BrainService()
    response = service.execute(BrainRequest(message="Build a simple task management API with authentication"))
    assert response.success is True
    state = response.state
    assert state.goal.primary_goal
    assert state.objective.primary_objective
    assert state.context.project_type in {"api", "application", "general"}
    assert state.plan is not None or state.planner.execution_steps or state.decision.next_action
