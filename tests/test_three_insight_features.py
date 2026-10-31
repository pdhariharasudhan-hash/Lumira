from app.services.goals.goal_insights_service import GoalInsightsService
from app.services.work_items.workflow_insights_service import WorkflowInsightsService
from app.services.notifications.notification_insights_service import NotificationInsightsService


class FakeMemory:
    def get_all(self):
        return {"goals": [{"status": "active", "progress": 50}, {"status": "completed", "progress": 100}]}


class FakeWorkflows:
    def list_workflows(self, **kwargs):
        return [{"status": "in_progress", "tasks": [{"status": "completed"}, {"status": "blocked"}]}]


class FakeNotifications:
    def list(self):
        return {"notifications": [{"status": "unread", "level": "warning"}, {"status": "read", "level": "info"}]}


def test_three_insight_features():
    assert GoalInsightsService(FakeMemory()).summary()["average_progress"] == 75.0
    workflow = WorkflowInsightsService(FakeWorkflows()).summary()
    assert workflow["task_completion_rate"] == 50.0
    assert NotificationInsightsService(FakeNotifications()).summary()["unread"] == 1
