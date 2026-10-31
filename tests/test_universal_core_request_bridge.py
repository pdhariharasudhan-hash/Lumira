from types import SimpleNamespace

from app.services.system.core_request_bridge_service import CoreRequestBridgeService


class FakeRuntime:
    def execution_context(self, operation, session_id=None, project_id=None, goal_id=None):
        return {
            "success": True,
            "operation": operation,
            "context": {
                "session_id": session_id,
                "project_id": project_id,
                "goal_id": goal_id,
            },
        }


def test_universal_request_bridge_uses_query_and_headers(monkeypatch):
    from app.services.system import core_request_bridge_service
    monkeypatch.setattr(core_request_bridge_service, "CoreRuntimeBridgeService", lambda: FakeRuntime())

    request = SimpleNamespace(
        query_params={"session_id": "s1", "project_id": "p1"},
        headers={"x-lumira-goal-id": "g1"},
        url=SimpleNamespace(path="/images/generate"),
    )
    result = CoreRequestBridgeService().build(request)
    assert result["context"] == {
        "session_id": "s1",
        "project_id": "p1",
        "goal_id": "g1",
    }
