from datetime import datetime, timezone, timedelta
from app.services.goals.goal_attention_service import GoalAttentionService
from app.services.system.event_insights_service import EventInsightsService
from app.services.work_items.next_action_service import NextActionService


class FakeMemory:
    def get_all(self):
        return {"goals":[{"goal_id":"g1","title":"Late","status":"active","deadline":(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),"blockers":[]}]}


class FakeEvents:
    def recent(self, limit):
        return {"events":[{"event":"brain_execution_completed","source":"brain"},{"event":"brain_execution_failed","source":"brain"}]}


class FakeWork:
    def list_workflows(self, **kwargs):
        return [{"workflow_id":"w1","project_id":"p1","goal_id":"g1","tasks":[
            {"task_id":"a","title":"first","status":"completed","dependencies":[]},
            {"task_id":"b","title":"next","status":"pending","dependencies":["a"]},
            {"task_id":"c","title":"later","status":"pending","dependencies":["b"]}]}]


def test_goal_attention_event_analytics_and_next_actions():
    assert GoalAttentionService(FakeMemory()).attention()["count"] == 1
    assert EventInsightsService(FakeEvents()).summary()["failure_events"] == 1
    actions = NextActionService(FakeWork()).ready()["actions"]
    assert [item["task_id"] for item in actions] == ["b"]
