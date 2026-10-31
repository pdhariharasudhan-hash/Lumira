from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService


class Status:
    def overview(self): return {}
    def snapshot(self): return {}
class Features:
    def overview(self): return {}
class Resources:
    def snapshot(self): return {}
class Artifacts:
    def stats(self): return {}
class Voice:
    def status(self): return {}
class Sessions:
    def get_session(self, value): return {}
class Memory:
    def get_all(self): return {}
class Recovery:
    def summary(self): return {}
    def resume(self, value): return None
class Learning: pass
class Projects:
    def list_projects(self): return {"projects": [{"name": "lumira"}]}
class Devices:
    def list_devices(self, limit=200): return [{"status": "online"}, {"status": "offline"}]
class Search:
    def search_all(self, query): return {"items": [{"title": query}, {"title": "other"}]}


def test_runtime_bridge_includes_projects_devices_and_search():
    service = CoreRuntimeBridgeService(
        Status(), Features(), Resources(), Artifacts(), Voice(), Sessions(),
        Memory(), Recovery(), Learning(), Projects(), Devices(), Search()
    )
    result = service.overview()
    assert result["projects"]["data"]["total"] == 1
    assert result["devices"]["data"]["statuses"]["online"] == 1
    search = service.search_context("test", 1)
    assert search["count"] == 1
