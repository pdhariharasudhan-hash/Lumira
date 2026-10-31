from app.services.notifications.notification_service import NotificationService
from app.services.tasks.task_insights_service import TaskInsightsService
from app.services.system.core_diagnostics_service import CoreDiagnosticsService


class FakeTasks:
    def list(self):
        return {"tasks": [{"status": "pending"}, {"status": "completed"}, {"status": "completed"}]}


class FakeHealth:
    def snapshot(self):
        return {"success": True, "status": "healthy"}


class FakeEvents:
    def recent(self, limit):
        return {"events": [{"event": "brain_execution_completed"}, {"event": "quick_task_completed"}]}


def test_three_feature_batch(tmp_path):
    notifications = NotificationService(tmp_path / "notifications.json")
    first = notifications.create("one")
    notifications.create("two")
    assert notifications.mark_all_read()["marked_read"] == 2
    assert notifications.delete(first["notification"]["id"])["success"] is True

    insights = TaskInsightsService(FakeTasks()).summary()
    assert insights["completion_rate"] == 66.67

    diagnostics = CoreDiagnosticsService(FakeHealth(), FakeEvents()).snapshot()
    assert diagnostics["status"] == "healthy"
    assert diagnostics["recent_event_count"] == 2
