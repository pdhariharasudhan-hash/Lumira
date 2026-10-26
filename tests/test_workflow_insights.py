from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

import app.routes.workflow_insights as route


def task(task_id, status="pending", dependencies=None, history=None, **extra):
    now = datetime.now(UTC).isoformat()
    return {
        "task_id": task_id, "title": f"Task {task_id}", "status": status,
        "dependencies": dependencies or [], "blocker": None, "result": None,
        "history": history or [{"status": status, "at": now}], "created_at": now,
        "updated_at": now, **extra,
    }


def workflow(workflow_id="wf-1", status="in_progress", tasks=None, **extra):
    now = datetime.now(UTC).isoformat()
    return {
        "workflow_id": workflow_id, "title": f"Workflow {workflow_id}",
        "request": "Manage a workflow", "category": "operations", "status": status,
        "project_id": "lumira", "goal_id": None, "tasks": tasks or [task("t1", "in_progress")],
        "created_at": now, "updated_at": now, **extra,
    }


class FakeService:
    def __init__(self, workflows):
        self.items = [workflow for workflow in workflows]

    def list_workflows(self, *, limit=50, category=None, project_id=None, **filters):
        items = self.items
        if category:
            items = [item for item in items if item["category"] == category]
        if project_id:
            items = [item for item in items if item.get("project_id") == project_id]
        return items[:limit]

    def get_workflow(self, workflow_id):
        return next((item for item in self.items if item["workflow_id"] == workflow_id), None)

    def update_task(self, workflow_id, task_id, status, blocker=None, result=None):
        wf = self.get_workflow(workflow_id)
        if wf is None:
            raise KeyError("workflow not found")
        target = next((item for item in wf["tasks"] if item["task_id"] == task_id), None)
        if target is None:
            raise KeyError("task not found")
        if status == "in_progress" and any(
            dep not in {t["task_id"] for t in wf["tasks"] if t["status"] == "completed"}
            for dep in target["dependencies"]
        ):
            raise ValueError("dependencies incomplete")
        target.update(status=status, blocker=blocker, result=result)
        wf["status"] = route.WorkItemService._status_for_tasks(wf["tasks"])
        return wf


@pytest.fixture
def fake_service(monkeypatch):
    instance = FakeService([
        workflow("blocked", "blocked", [task("a", "blocked", history=[
            {"status": "pending", "at": (datetime.now(UTC) - timedelta(days=2)).isoformat()},
            {"status": "blocked", "at": datetime.now(UTC).isoformat()},
        ])]),
        workflow("failed", "failed", [task("b", "failed")]),
        workflow("ready", "planned", [task("c", "pending")]),
    ])
    monkeypatch.setattr(route, "_service", lambda: instance)
    return instance


def test_summary_counts_workflow_and_task_states(fake_service):
    result = route.workflow_summary(category="operations")
    assert result["scanned_workflows"] == 3
    assert result["workflow_status_counts"]["failed"] == 1
    assert result["task_status_counts"]["blocked"] == 1


def test_attention_prioritizes_failed_and_blocked(fake_service):
    result = route.workflow_attention(limit=10)
    ids = [item["workflow_id"] for item in result["items"]]
    assert ids.index("failed") < ids.index("blocked")
    assert "ready" not in ids


def test_search_matches_task_titles_and_filters_status(fake_service):
    result = route.search_workflows(q="TASK B", status="failed")
    assert result["total"] == 1
    assert result["workflows"][0]["workflow_id"] == "failed"


def test_export_is_bounded_and_has_schema_version(fake_service):
    result = route.export_workflows(limit=2)
    assert result["schema_version"] == 1
    assert result["count"] == 2
    assert result["truncated"] is True


def test_dependency_graph_exposes_nodes_and_edges(fake_service):
    wf = workflow("graph", tasks=[task("a", "completed"), task("b", dependencies=["a"])])
    fake_service.items.append(wf)
    result = route.workflow_dependency_graph("graph")
    assert result["node_count"] == 2
    assert result["edges"] == [{"from": "a", "to": "b"}]


def test_retry_requires_failed_task_and_resets_to_pending(fake_service):
    result = route.retry_failed_task("failed", "b")
    assert result["retried_task_id"] == "b"
    assert result["workflow"]["tasks"][0]["status"] == "pending"
    with pytest.raises(HTTPException) as error:
        route.retry_failed_task("ready", "c")
    assert error.value.status_code == 409


def test_unblock_rejects_unmet_dependencies(fake_service):
    wf = workflow("deps", "blocked", [task("a", "blocked", dependencies=["b"]), task("b", "pending")])
    fake_service.items.append(wf)
    with pytest.raises(HTTPException) as error:
        route.unblock_task("deps", "a")
    assert error.value.status_code == 409


def test_start_requires_all_dependencies_completed(fake_service):
    wf = workflow("deps", "planned", [task("a", "pending", dependencies=["b"]), task("b", "pending")])
    fake_service.items.append(wf)
    with pytest.raises(HTTPException) as error:
        route.start_ready_task("deps", "a")
    assert error.value.status_code == 409


def test_timeline_ignores_old_events(fake_service):
    result = route.workflow_timeline(days=1)
    assert all(datetime.fromisoformat(event["at"].replace("Z", "+00:00")) >= datetime.now(UTC) - timedelta(days=1) for event in result["events"])
