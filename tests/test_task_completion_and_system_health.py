from app.services.tasks.quick_task_service import QuickTaskService
from app.services.system.system_health_service import SystemHealthService


class FakeRuntime:
    def execution_context(self, *args, **kwargs):
        return {"success": True, "context": {"session_id": kwargs.get("session_id")}}


class FakeEvents:
    def __init__(self): self.calls = []
    def record(self, *args, **kwargs):
        self.calls.append(args)
        return {"event_record": {"event": args[0], "source": args[1], "core_context": {"context": {}}}}
    def recent(self, limit): return {"events": []}


class FakeNotifications:
    def __init__(self): self.calls = []
    def create_from_core_event(self, event): self.calls.append(event); return {"success": True}
    def list(self, unread_only=False): return {"notifications": []}


def test_task_completion_and_health_features(tmp_path, monkeypatch):
    from app.services.system import core_runtime_bridge_service
    monkeypatch.setattr(core_runtime_bridge_service, "CoreRuntimeBridgeService", lambda: FakeRuntime())
    events, notifications = FakeEvents(), FakeNotifications()
    tasks = QuickTaskService(tmp_path / "tasks.json", events, notifications)

    task = tasks.create("Finish integration", "s1")
    assert tasks.complete(task["task"]["id"])["success"] is True
    assert events.calls[0][0] == "quick_task_completed"
    assert len(notifications.calls) == 1

    health = SystemHealthService(events, notifications).snapshot()
    assert health["status"] == "healthy"
