import json
from copy import deepcopy

import pytest
from fastapi import HTTPException

import app.routes.workflows as route


def make_workflow():
    return {
        "workflow_id": "wf-agent",
        "title": "Build a feature",
        "request": "Implement a small feature in Lumira",
        "category": "operations",
        "status": "planned",
        "project_id": "lumira",
        "goal_id": None,
        "tasks": [
            {"task_id": "task-1", "title": "Research requirements", "status": "pending",
             "dependencies": [], "blocker": None, "result": None},
            {"task_id": "task-2", "title": "Create implementation plan", "status": "pending",
             "dependencies": ["task-1"], "blocker": None, "result": None},
            {"task_id": "task-3", "title": "Implement the feature", "status": "pending",
             "dependencies": ["task-2"], "blocker": None, "result": None},
        ],
    }


class FakeWorkItemService:
    def __init__(self):
        self.workflow = make_workflow()

    def get_workflow(self, workflow_id):
        return deepcopy(self.workflow) if workflow_id == self.workflow["workflow_id"] else None

    def update_task(self, workflow_id, task_id, status, blocker=None, result=None):
        assert workflow_id == self.workflow["workflow_id"]
        task = next(item for item in self.workflow["tasks"] if item["task_id"] == task_id)
        if status in {"in_progress", "completed"}:
            completed = {item["task_id"] for item in self.workflow["tasks"] if item["status"] == "completed"}
            assert set(task["dependencies"]).issubset(completed)
        task.update(status=status, blocker=blocker, result=result)
        states = {item["status"] for item in self.workflow["tasks"]}
        self.workflow["status"] = "completed" if states == {"completed"} else "failed" if "failed" in states else "blocked" if "blocked" in states else "in_progress" if states.intersection({"in_progress", "completed"}) else "planned"
        return deepcopy(self.workflow)

    def get_workflow_progress(self, workflow_id):
        tasks = self.workflow["tasks"]
        completed = {task["task_id"] for task in tasks if task["status"] == "completed"}
        return {
            "workflow_id": workflow_id,
            "ready_tasks": [task["task_id"] for task in tasks
                            if task["status"] == "pending" and set(task["dependencies"]).issubset(completed)],
            "completed_count": len(completed),
        }


class FakeArtifactManager:
    def create_artifact(self, artifact_type, content, source, extension="txt"):
        return {"artifact_id": "artifact-" + source.rsplit(":", 1)[-1], "type": artifact_type}


class FakeAgentManager:
    def __init__(self, timeout_seconds=20.0, outcomes=None):
        self.outcomes = list(outcomes or [])
        self.prompts = []
        self.forced_agents = []

    def run(self, agent_name, prompt):
        self.forced_agents.append(agent_name)
        self.prompts.append(prompt)
        return {"success": True, "agent": agent_name, "result": {"summary": "forced agent completed"}}

    def dispatch(self, prompt):
        self.prompts.append(prompt)
        if self.outcomes:
            return self.outcomes.pop(0)
        return {"success": True, "agent": "planner_agent", "result": {"summary": "step completed"}}


@pytest.fixture
def agent_route(monkeypatch):
    service = FakeWorkItemService()
    manager = FakeAgentManager()
    monkeypatch.setattr(route, "WorkItemService", lambda: service)
    monkeypatch.setattr(route, "AgentManager", lambda timeout_seconds=20.0: manager)
    monkeypatch.setattr(route, "ArtifactManagerService", FakeArtifactManager)
    return service, manager


def test_run_ready_executes_dependency_chain_and_persists_results(agent_route):
    service, manager = agent_route
    result = route.run_ready_workflow_tasks("wf-agent", route.WorkflowAgentRunRequest(max_tasks=3))

    assert result["success"] is True
    assert result["executed_count"] == 3
    assert [task["status"] for task in service.workflow["tasks"]] == ["completed"] * 3
    assert len(manager.prompts) == 3
    assert all("Overall request:" in prompt and "Step:" in prompt for prompt in manager.prompts)
    assert json.loads(service.workflow["tasks"][0]["result"])["agent_outcome"]["success"] is True
    assert json.loads(service.workflow["tasks"][0]["result"])["artifact_storage"] == "recorded"


def test_run_ready_stops_after_failure_and_leaves_dependents_pending(agent_route):
    service, manager = agent_route
    manager.outcomes = [{"success": False, "state": "rejected", "code": "no_matching_agent",
                         "message": "No matching agent."}]

    result = route.run_ready_workflow_tasks("wf-agent", route.WorkflowAgentRunRequest(max_tasks=3))

    assert result["success"] is False
    assert result["stop_reason"] == "agent_task_failed"
    assert service.workflow["tasks"][0]["status"] == "failed"
    assert service.workflow["tasks"][1]["status"] == "pending"
    assert service.workflow["tasks"][2]["status"] == "pending"


def test_run_ready_rejects_unknown_workflow(agent_route):
    with pytest.raises(HTTPException) as error:
        route.run_ready_workflow_tasks("missing", route.WorkflowAgentRunRequest())
    assert error.value.status_code == 404



def test_execution_preview_is_read_only_and_marks_dependency_readiness(agent_route):
    service, manager = agent_route
    before = deepcopy(service.workflow)
    result = route.preview_workflow_execution("wf-agent")

    assert result["mode"] == "preview_only"
    assert result["agent_calls"] == 0
    assert result["state_changed"] is False
    assert result["ready_count"] == 1
    assert result["tasks"][0]["ready"] is True
    assert result["tasks"][1]["unmet_dependencies"] == ["task-1"]
    assert service.workflow == before
    assert manager.prompts == []


def test_goal_runner_respects_one_shared_task_budget(monkeypatch):
    workflows = [
        {"workflow_id": "wf-one", "title": "First", "status": "planned"},
        {"workflow_id": "wf-two", "title": "Second", "status": "planned"},
    ]
    monkeypatch.setattr(route.WorkItemService, "list_workflows", lambda self, **kwargs: workflows)
    calls = []

    def fake_run(workflow_id, request):
        calls.append((workflow_id, request.max_tasks))
        return {
            "success": True,
            "stop_reason": "task_limit_reached",
            "outcomes": [{"task_id": f"{workflow_id}-task", "success": True}],
        }

    monkeypatch.setattr(route, "run_ready_workflow_tasks", fake_run)
    result = route.run_goal_ready_workflows("goal-1", route.WorkflowGoalRunRequest(max_tasks=2))

    assert result["success"] is True
    assert result["task_outcomes_count"] == 2
    assert calls == [("wf-one", 2), ("wf-two", 1)]


def test_goal_runner_returns_not_found_when_no_linked_workflows(monkeypatch):
    monkeypatch.setattr(route.WorkItemService, "list_workflows", lambda self, **kwargs: [])
    with pytest.raises(HTTPException) as error:
        route.run_goal_ready_workflows("goal-missing", route.WorkflowGoalRunRequest())
    assert error.value.status_code == 404



def test_run_ready_supports_explicit_agent_selection(agent_route):
    service, manager = agent_route
    result = route.run_ready_workflow_tasks(
        "wf-agent",
        route.WorkflowAgentRunRequest(max_tasks=1, agent_mode="research_agent"),
    )

    assert result["success"] is True
    assert manager.forced_agents == ["research_agent"]
    assert manager.prompts



def test_retry_failed_tasks_requeues_without_invoking_agents(agent_route):
    service, manager = agent_route
    service.workflow["tasks"][0]["status"] = "failed"
    service.workflow["tasks"][0]["blocker"] = "agent failed"
    service.workflow["status"] = "failed"

    result = route.reset_failed_workflow_tasks(
        "wf-agent", route.WorkflowRetryFailedRequest(max_tasks=5)
    )

    assert result["reset_count"] == 1
    assert service.workflow["tasks"][0]["status"] == "pending"
    assert manager.prompts == []
    assert result["note"].startswith("Requeued tasks remain subject to dependency checks")
