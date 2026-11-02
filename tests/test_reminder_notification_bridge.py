from datetime import datetime, timedelta, timezone

from app.services.reminders.reminder_service import ReminderService


class FakeNotificationService:
    def __init__(self):
        self.calls = []

    def create(self, message, level, **context):
        self.calls.append((message, level, context))
        return {"success": True, "notification": {"id": "notification-1"}}


class FakeRuntime:
    def execution_context(self, *args, **kwargs):
        return {
            "success": True,
            "context": {
                "session_id": kwargs.get("session_id"),
                "project_id": kwargs.get("project_id"),
                "goal_id": kwargs.get("goal_id"),
            },
        }


def test_due_reminder_creates_notification_with_core_context(tmp_path, monkeypatch):
    from app.services.system import core_runtime_bridge_service
    monkeypatch.setattr(core_runtime_bridge_service, "CoreRuntimeBridgeService", lambda: FakeRuntime())

    notifications = FakeNotificationService()
    service = ReminderService(tmp_path / "reminders.json", notification_service=notifications)
    due_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    service.create("Build Lumira", due_at, "s1", "p1", "g1")

    result = service.due()

    assert len(result["reminders"]) == 1
    assert result["reminders"][0]["notification_id"] == "notification-1"
    assert notifications.calls[0][0] == "Build Lumira"
    assert notifications.calls[0][2]["session_id"] == "s1"
