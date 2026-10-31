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
    def get_session(self, value): return {"id": value}
class Memory:
    def get_all(self): return {}
class Recovery:
    def summary(self): return {}
    def resume(self, value): return None
class Learning: pass
class Projects:
    def list_projects(self): return {"projects": []}
class Devices:
    def list_devices(self, limit=200): return []
class Search:
    def search_all(self, query): return {"items": []}
class Agents:
    def list_agents(self): return ["planner_agent", "research_agent"]
class PersonalContext:
    def snapshot(self, query, limit): return {"notes": [{"id": "n"}], "projects": []}


def test_core_runtime_bridges_agents_and_personal_context():
    service = CoreRuntimeBridgeService(
        Status(), Features(), Resources(), Artifacts(), Voice(), Sessions(),
        Memory(), Recovery(), Learning(), Projects(), Devices(), Search(),
        Agents(), PersonalContext()
    )
    overview = service.overview()
    assert overview["agents"]["data"]["total"] == 2
    assert overview["personal_context"]["data"]["note_count"] == 1
    context = service.agent_context("plan this", "s1", "p1", "g1")
    assert context["success"] is True
    assert context["core_context"]["session_id"] == "s1"
