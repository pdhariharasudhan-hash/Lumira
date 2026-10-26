from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

import app.routes.goal_intelligence as route


def make_goal(goal_id, **updates):
    now = datetime.now(UTC).isoformat()
    value = {
        "goal_id": goal_id, "title": goal_id, "objective": "A measurable objective",
        "status": "active", "priority": "normal", "progress": 0,
        "dependencies": [], "blockers": [], "milestones": [], "artifact_ids": [],
        "project_id": "lumira", "deadline": None, "created_at": now, "updated_at": now,
        "history": [],
    }
    value.update(updates)
    return value


class FakeMemory:
    def __init__(self, goals):
        self.goals = [dict(goal) for goal in goals]
        self.cognitive_store = self

    def get_all(self):
        return {"goals": [dict(goal) for goal in self.goals]}

    def update_goal(self, goal_id, **updates):
        goal = next((item for item in self.goals if item["goal_id"] == goal_id), None)
        if goal is None:
            raise KeyError(goal_id)
        goal.update(updates)
        return dict(goal)

    def create_goal(self, **fields):
        goal = make_goal(f"new-{len(self.goals) + 1}", **fields)
        self.goals.append(goal)
        return dict(goal)

    def decompose_goal(self, goal_id, objectives):
        parent = next(g for g in self.goals if g["goal_id"] == goal_id)
        children = []
        for title in objectives:
            child = make_goal(f"child-{len(self.goals) + 1}", title=title, parent_goal_id=goal_id)
            self.goals.append(child)
            children.append(child)
        return {"parent": parent, "objectives": children}

    def archive(self, collection, record_id):
        goal = next((g for g in self.goals if g["goal_id"] == record_id), None)
        if not goal:
            return False
        goal["archived"] = True
        return True

    def update(self, callback, default):
        return callback({"goals": self.goals})


def test_goal_intelligence_exposes_28_deterministic_signals(monkeypatch):
    monkeypatch.setattr(route, "MemoryService", lambda: FakeMemory([
        make_goal("active"),
        make_goal("overdue", deadline=(datetime.now(UTC) - timedelta(days=2)).isoformat()),
        make_goal("blocked", status="blocked", blockers=["waiting"], priority="urgent"),
        make_goal("done", status="completed", progress=100),
    ]))
    result = route.get_goal_intelligence()
    signals = result["signals"]
    assert len(signals) == 28
    assert signals["01_total_goals"] == 4
    assert signals["04_completed_goals"] == 1
    assert "overdue" in signals["11_overdue_goal_ids"]
    assert "blocked" in signals["20_blocked_or_has_blockers_ids"]


def test_goal_search_is_case_insensitive_and_status_scoped(monkeypatch):
    monkeypatch.setattr(route, "MemoryService", lambda: FakeMemory([
        make_goal("a", title="Build Lumira Voice"),
        make_goal("b", title="Build Lumira UI", status="paused"),
    ]))
    result = route.search_goals(q="LUMIRA", status="paused")
    assert result["total"] == 1
    assert result["goals"][0]["goal_id"] == "b"


def test_goal_timeline_ignores_malformed_dates_and_applies_window(monkeypatch):
    monkeypatch.setattr(route, "MemoryService", lambda: FakeMemory([
        make_goal("a", history=[
            {"event": "recent", "at": datetime.now(UTC).isoformat()},
            {"event": "bad", "at": "not-a-date"},
            {"event": "old", "at": (datetime.now(UTC) - timedelta(days=90)).isoformat()},
        ])
    ]))
    result = route.get_goal_timeline(days=7)
    assert [event["event"] for event in result["events"]] == ["recent"]


def test_next_actions_excludes_unmet_dependencies_and_blockers(monkeypatch):
    monkeypatch.setattr(route, "MemoryService", lambda: FakeMemory([
        make_goal("ready", priority="high", progress=20),
        make_goal("blocked", blockers=["approval"]),
        make_goal("dependent", dependencies=["not-done"]),
        make_goal("not-done", status="active"),
    ]))
    result = route.get_goal_next_actions()
    ids = [item["goal"]["goal_id"] for item in result["actions"]]
    assert "ready" in ids
    assert "blocked" not in ids
    assert "dependent" not in ids


def test_milestone_lifecycle_is_bounded_and_persistent(monkeypatch):
    memory = FakeMemory([make_goal("a")])
    monkeypatch.setattr(route, "MemoryService", lambda: memory)
    created = route.add_goal_milestone("a", route.MilestoneCreate(title="First checkpoint"))
    milestone_id = created["milestone"]["milestone_id"]
    updated = route.update_goal_milestone("a", milestone_id, status="completed")
    assert updated["status"] == "completed"
    listed = route.list_goal_milestones("a")
    assert listed["milestones"][0]["completed_at"]
    removed = route.remove_goal_milestone("a", milestone_id)
    assert removed["goal"]["milestones"] == []


def test_bulk_completion_rejects_unmet_dependency(monkeypatch):
    monkeypatch.setattr(route, "MemoryService", lambda: FakeMemory([
        make_goal("a", dependencies=["b"]),
        make_goal("b", status="active"),
    ]))
    request = route.BulkGoalUpdate(goal_ids=["a"], status="completed")
    with pytest.raises(HTTPException) as error:
        route.bulk_update_goals(request)
    assert error.value.status_code == 409


def test_goal_comparison_returns_field_differences(monkeypatch):
    monkeypatch.setattr(route, "MemoryService", lambda: FakeMemory([
        make_goal("a", title="Alpha", priority="low"),
        make_goal("b", title="Beta", priority="high"),
    ]))
    result = route.compare_goals("a", "b")
    assert result["difference_count"] >= 2
    assert result["differences"]["priority"] == {"left": "low", "right": "high"}


def test_rollup_aggregates_children_without_mutating_parent(monkeypatch):
    memory = FakeMemory([
        make_goal("parent", progress=10),
        make_goal("child-a", parent_goal_id="parent", progress=50),
        make_goal("child-b", parent_goal_id="parent", progress=100, status="completed"),
    ])
    monkeypatch.setattr(route, "MemoryService", lambda: memory)
    result = route.get_goal_rollup("parent")
    assert result["child_count"] == 2
    assert result["average_child_progress"] == 75
    assert result["completed_child_percent"] == 50
    assert next(g for g in memory.goals if g["goal_id"] == "parent")["progress"] == 10
