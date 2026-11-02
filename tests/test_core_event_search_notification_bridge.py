from app.services.notifications.notification_service import NotificationService
from app.services.system.core_event_log_service import CoreEventLogService


class FakeRuntime:
    def execution_context(self, *args, **kwargs):
        return {"success": True, "context": {"session_id": kwargs.get("session_id")}}


def test_event_search_and_notification_bridge(tmp_path, monkeypatch):
    from app.services.system import core_runtime_bridge_service
    monkeypatch.setattr(core_runtime_bridge_service, "CoreRuntimeBridgeService", lambda: FakeRuntime())

    events = CoreEventLogService(tmp_path / "events.json")
    notifications = NotificationService(tmp_path / "notifications.json")

    recorded = events.record("workflow_completed", "workflow", session_id="s1")
    events.record("task_created", "tasks")
    assert events.search(event="workflow")["count"] == 1

    created = notifications.create_from_core_event(recorded)
    assert created["success"] is True
    assert created["notification"]["core_context"]["success"] is True
