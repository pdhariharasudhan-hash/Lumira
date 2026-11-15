from fastapi.testclient import TestClient

from app.main import app
from app.services.capabilities.capability_router_service import CapabilityRouterService
from app.services.brain.brain_response import BrainResponse
from app.services.brain.brain_state import BrainState


def test_command_executes_parsed_capability_through_brain(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    expected_result = {
        "success": True,
        "capability": "search",
        "results": [],
    }
    state = BrainState()
    state.execution_result = expected_result

    class FakeBrain:
        def execute(self, request):
            assert request.metadata["execute_capability"] == "search"
            payload = request.metadata["capability_payload"]
            assert payload["query"] == "cats"
            assert payload["session_id"] == request.session_id
            assert "autonomous" in request.metadata
            return BrainResponse(success=True, state=state)

    monkeypatch.setattr("app.routes.command.BrainService", FakeBrain)
    monkeypatch.setattr(
        CapabilityRouterService,
        "__init__",
        lambda self: (_ for _ in ()).throw(
            AssertionError("/command must not execute capabilities outside Brain")
        ),
    )

    response = TestClient(app).post("/command", json={"input": "search cats"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["result"] == expected_result
