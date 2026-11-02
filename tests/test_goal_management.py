from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

import app.routes.goals as route


class GoalMemory:
    def __init__(self, goals):
        self.goals = deepcopy(goals)

    def get_all(self):
        return {"goals": deepcopy(self.goals)}

    def update_goal(self, goal_id, **updates):
        goal = next((item for item in self.goals if item["goal_id"] == goal_id), None)
        if goal is None:
            raise KeyError(goal_id)
        goal.update(deepcopy(updates))
        return deepcopy(goal)


def goal(goal_id, **updates):
    item = {
        "goal_id": goal_id,
        "title": goal_id,
        "status": "active",
        "priority": "normal",
        "progress": 0,
        "dependencies": [],
        "blockers": [],
        "deadline": None,
        "archived": False,
    }
    item.update(updates)
    return item


def test_goal_summary_counts_status_priority_and_overdue(monkeypatch):
    memory = GoalMemory([
        goal("a", status="active", priority="urgent", deadline=(datetime.now(UTC) - timedelta(days=1)).isoformat()),
        goal("b", status="blocked", blockers=["waiting"]),
        goal("c", status="completed", priority="high"),
    ])
    monkeypatch.setattr(route, "MemoryService", lambda: memory)
    result = route.get_goals_summary()
    assert result["total"] == 3
    assert result["by_status"]["active"] == 1
    assert result["by_status"]["blocked"] == 1
    assert result["by_priority"]["urgent"] == 1
    assert result["overdue"] == 1


def test_dependency_graph_reports_missing_dependency_and_cycle():
    memory = GoalMemory([
        goal("a", dependencies=["b", "missing"]),
        goal("b", dependencies=["a"]),
    ])
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(route, "MemoryService", lambda: memory)
    result = route.get_goal_dependencies("a")
    assert any(item["code"] == "dependency_cycle" for item in result["warnings"])
    assert any(item["code"] == "missing_dependency" for item in result["warnings"])
    monkeypatch.undo()


def test_add_goal_dependency_prevents_self_and_transitive_cycles(monkeypatch):
    memory = GoalMemory([goal("a", dependencies=["b"]), goal("b", dependencies=["c"]), goal("c")])
    monkeypatch.setattr(route, "MemoryService", lambda: memory)
    with pytest.raises(HTTPException) as self_cycle:
        route.add_goal_dependency("a", route.GoalDependencyRequest(dependency_goal_id="a"))
    assert self_cycle.value.status_code == 409
    with pytest.raises(HTTPException) as cycle:
        route.add_goal_dependency("c", route.GoalDependencyRequest(dependency_goal_id="a"))
    assert cycle.value.status_code == 409


def test_add_dependency_is_idempotent_and_remove_dependency_persists(monkeypatch):
    memory = GoalMemory([goal("a"), goal("b")])
    monkeypatch.setattr(route, "MemoryService", lambda: memory)
    request = route.GoalDependencyRequest(dependency_goal_id="b")
    assert route.add_goal_dependency("a", request)["changed"] is True
    assert route.add_goal_dependency("a", request)["changed"] is False
    result = route.remove_goal_dependency("a", dependency_goal_id="b")
    assert result["goal"]["dependencies"] == []


def test_blocker_add_is_idempotent_and_remove_is_exact(monkeypatch):
    memory = GoalMemory([goal("a")])
    monkeypatch.setattr(route, "MemoryService", lambda: memory)
    request = route.GoalBlockerRequest(blocker="Need approval")
    assert route.add_goal_blocker("a", request)["changed"] is True
    assert route.add_goal_blocker("a", request)["changed"] is False
    result = route.remove_goal_blocker("a", blocker="Need approval")
    assert result["goal"]["blockers"] == []


def test_goal_blocker_removal_returns_not_found_for_unknown_blocker(monkeypatch):
    memory = GoalMemory([goal("a", blockers=["Known issue"])])
    monkeypatch.setattr(route, "MemoryService", lambda: memory)
    with pytest.raises(HTTPException) as error:
        route.remove_goal_blocker("a", blocker="unknown")
    assert error.value.status_code == 404
