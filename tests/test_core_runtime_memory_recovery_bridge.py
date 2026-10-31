from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService


class Status:
    def overview(self): return {"ok": True}
    def snapshot(self): return {"ok": True}
class Features:
    def overview(self): return {"success": True}
class Resources:
    def snapshot(self): return {}
class Artifacts:
    def stats(self): return {}
class Voice:
    def status(self): return {}
class Sessions:
    def get_session(self, value): return {"id": value}
class Memory:
    def get_all(self):
        return {"goals": [1], "decisions": [1, 2], "experiences": [], "learning_records": [1]}
class Recovery:
    def summary(self): return {"total": 1}
    def resume(self, workflow_id): return {"workflow_id": workflow_id}
class Learning:
    pass


def test_core_runtime_bridges_memory_and_recovery():
    bridge = CoreRuntimeBridgeService(Status(), Features(), Resources(), Artifacts(), Voice(), Sessions(), Memory(), Recovery(), Learning())
    overview = bridge.overview()
    assert overview["memory"]["data"]["goals"] == 1
    assert overview["recovery"]["data"]["total"] == 1
    checkpoint = bridge.checkpoint_context("run-1")
    assert checkpoint["checkpoint"]["workflow_id"] == "run-1"
