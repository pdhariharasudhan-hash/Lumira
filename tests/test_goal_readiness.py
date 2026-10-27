from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

import app.routes.goals as goals_route


class FakeMemory:
    def __init__(self, goals):
        self.goals = goals

    def get_all(self):
        return {"goals": self.goals}


class FakeWorkItems:
    def __init__(self, workflows):
        self.workflows = workflows

    def list_workflows(self, *, goal_id=None, limit=50):
        workflows = self.workflows
        if goal_id:
            workflows = [item for item in workflows if item.get("goal_id") == goal_id]
        return workflows[:limit]


def _goal(**overrides):
    result = {
        "goal_id": "goal-1",
        "title": "Build feature",
        "status": "active",
        "progress": 0,
        "dependencies": [],
        "blockers": [],
        "deadline": None,
        "archived": False,
    }
    result.update(overrides)
    return result


def test_goal_readiness_reports_unmet_dependency_and_active_workflow(monkeypatch):
    goals = [
        _goal(dependencies=["goal-2"]),
        _goal(goal_id="goal-2", title="Prerequisite", status="blocked"),
    ]
    workflows = [{
        "workflow_id": "workflow-1",
        "goal_id": "goal-1",
        "title": "Existing workflow",
        "status": "in_progress",
        "tasks": [
            {"status": "completed"},
            {"status": "failed"},
        ],
    }]
    monkeypatch.setattr(goals_route, "MemoryService", lambda: FakeMemory(goals))
    monkeypatch.setattr(goals_route, "WorkItemService", lambda: FakeWorkItems(workflows))

    result = goals_route.get_goal_readiness("goal-1")

    assert result["ready_to_execute"] is False
    assert result["ready_to_plan"] is False
    assert result["dependency_status"][0]["satisfied"] is False
    assert result["active_workflow_exists"] is True
    assert result["linked_workflows"][0]["completed_task_count"] == 1
    assert result["linked_workflows"][0]["failed_task_count"] == 1


def test_goal_readiness_handles_deadlines_and_missing_dependencies(monkeypatch):
    goal = _goal(
        dependencies=["missing-goal"],
        deadline=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
    )
    monkeypatch.setattr(goals_route, "MemoryService", lambda: FakeMemory([goal]))
    monkeypatch.setattr(goals_route, "WorkItemService", lambda: FakeWorkItems([]))

    result = goals_route.get_goal_readiness("goal-1")

    assert result["ready_to_execute"] is False
    assert result["dependency_status"][0]["status"] == "missing"
    assert result["deadline"]["state"] == "overdue"


def test_goal_readiness_returns_not_found_for_unknown_goal(monkeypatch):
    monkeypatch.setattr(goals_route, "MemoryService", lambda: FakeMemory([]))
    monkeypatch.setattr(goals_route, "WorkItemService", lambda: FakeWorkItems([]))

    with pytest.raises(HTTPException) as error:
        goals_route.get_goal_readiness("unknown")

    assert error.value.status_code == 404



@pytest.mark.parametrize(
    ("goal", "expected_code"),
    [
        (_goal(blockers=["Awaiting prerequisite"]), "goal_blockers_present"),
        (_goal(status="paused"), "goal_not_active"),
    ],
)
def test_goal_planning_rejects_blocked_or_inactive_goals(monkeypatch, goal, expected_code):
    monkeypatch.setattr(goals_route, "MemoryService", lambda: FakeMemory([goal]))

    with pytest.raises(HTTPException) as error:
        goals_route.generate_goal_plan(goal["goal_id"])

    assert error.value.status_code == 409
    assert error.value.detail["code"] == expected_code
