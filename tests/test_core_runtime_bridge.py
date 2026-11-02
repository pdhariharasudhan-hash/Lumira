from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService


class Status:
    def overview(self): return {"system": "ready"}
    def snapshot(self): return {"system": "ready"}

class Features:
    def overview(self): return {"success": True, "features": {"total": 1}}

class Resources:
    def snapshot(self): return {"resource_pressure": "normal"}

class Artifacts:
    def stats(self): return {"total": 2}

class Voice:
    def status(self): return {"running": False}

class Sessions:
    def get_session(self, session_id): return {"session_id": session_id}


def test_runtime_bridge_aggregates_subsystems():
    service = CoreRuntimeBridgeService(Status(), Features(), Resources(), Artifacts(), Voice(), Sessions())
    result = service.overview()
    assert result["success"] is True
    assert result["resources"]["data"]["resource_pressure"] == "normal"
    context = service.context("s1", "p1", "g1")
    assert context["context"]["session"]["data"]["session_id"] == "s1"
