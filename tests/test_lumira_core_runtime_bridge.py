from app.core.lumira_core import LumiraCore


class FakeBridge:
    def context(self, session_id=None, project_id=None, goal_id=None):
        return {"success": True, "context": {"session_id": session_id, "project_id": project_id}}


def test_lumira_core_exposes_shared_runtime_context(monkeypatch):
    from app.services.system import core_runtime_bridge_service
    monkeypatch.setattr(core_runtime_bridge_service, "CoreRuntimeBridgeService", FakeBridge)
    core = LumiraCore()
    result = core.core_context("s1", "p1", "g1")
    assert result["context"]["session_id"] == "s1"
    assert result["context"]["project_id"] == "p1"
