from app.services.memory.memory_service import MemoryService
from app.services.memory.decision_lifecycle_service import DecisionLifecycleService
from app.services.work_items.action_priority_service import ActionPriorityService
from app.services.work_items.blocker_insights_service import BlockerInsightsService
from app.services.work_items.blocker_queue_service import BlockerQueueService


class FakeWorkItems:
    def list_workflows(self, limit=200):
        return [{
            "workflow_id": "wf-1",
            "title": "Build core",
            "project_id": "lumira",
            "goal_id": "goal-1",
            "tasks": [
                {"task_id": "t1", "title": "Implement API", "status": "failed",
                 "blocker": "Test failed", "dependencies": [], "updated_at": "2026-10-31T10:00:00+00:00"},
                {"task_id": "t2", "title": "Integrate API", "status": "pending",
                 "dependencies": ["t1"], "updated_at": "2026-10-31T10:00:00+00:00"},
            ],
        }]


class FakeMemory:
    def get_all(self):
        return {"goals": [{
            "goal_id": "goal-2", "title": "Build drone", "project_id": "electronics",
            "status": "active", "blockers": ["Waiting for motor driver"],
        }]}


def test_blocker_queue_detects_failed_tasks_dependencies_and_goal_blockers():
    queue = BlockerQueueService(FakeWorkItems(), FakeMemory())
    result = queue.list(limit=20)
    assert result["count"] == 3
    assert result["by_kind"]["failed_task"] == 1
    assert result["by_kind"]["dependency_failure"] == 1
    assert result["by_kind"]["goal_blocker"] == 1


def test_blocker_insights_enriches_severity():
    queue = BlockerQueueService(FakeWorkItems(), FakeMemory())
    result = BlockerInsightsService(queue).summary()
    assert result["by_severity"]["critical"] == 2
    assert result["by_severity"]["high"] == 1
    assert result["blockers"][0]["recommended_action"]


def test_adaptive_priority_has_explainable_scores():
    ranker = ActionPriorityService()
    result = ranker.rank(
        [{"task_id": "t1", "goal_id": "g1", "priority": "high", "status": "pending"}],
        attention=[{"goal_id": "g1"}],
        blockers=[],
    )
    action = result["actions"][0]
    assert 0 <= action["priority_score"] <= 100
    assert "linked_goal_needs_attention" in action["priority_reasons"]
    assert action["is_executable"] is True


def test_decision_outcome_is_persisted_without_auto_verifying_learning(tmp_path):
    memory = MemoryService(str(tmp_path / "project_memory.json"))
    decision = memory.record_decision(
        decision="Use FastAPI",
        reason="Existing backend already uses FastAPI",
        project_id="lumira",
        alternatives=["Flask", "Django"],
        confidence=0.9,
    )
    service = DecisionLifecycleService(memory)
    result = service.record_outcome(decision["decision_id"], "success", "Integration tests passed")
    assert result["decision"]["outcome_status"] == "success"
    assert result["decision"]["status"] == "reviewed"
    stored = memory._read_cognitive_memory()
    assert stored["experiences"][-1]["type"] == "success"
    assert stored["experiences"][-1]["verified"] is False
