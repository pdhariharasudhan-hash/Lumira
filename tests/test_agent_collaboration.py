from app.agents.agent_collaboration_service import AgentCollaborationService


class Manager:
    def __init__(self):
        self.calls = []

    def run(self, agent, task):
        self.calls.append((agent, task))
        return {"success": True, "state": "completed", "agent": agent}


def test_collaboration_is_structured_bounded_and_sequential():
    manager = Manager()
    service = AgentCollaborationService(manager)
    result = service.collaborate([
        {"agent": "planner_agent", "task": "Create a plan"},
        {"agent": "code_agent", "task": "Review the plan"},
    ])
    assert result["success"] is True
    assert manager.calls == [
        ("planner_agent", "Create a plan"),
        ("code_agent", "Review the plan"),
    ]


def test_collaboration_rejects_duplicate_tasks_and_evaluates_failures():
    service = AgentCollaborationService(Manager())
    duplicate = service.collaborate([
        {"agent": "planner_agent", "task": "same"},
        {"agent": "planner_agent", "task": "same"},
    ])
    assert duplicate["code"] == "duplicate_task"
    evaluation = service.evaluate([
        {"result": {"success": True}},
        {"result": {"success": False}},
    ])
    assert evaluation["success"] is False
    assert evaluation["accepted"] == 1
    assert evaluation["rejected"] == 1


def test_communication_validates_and_preserves_structured_messages():
    result = AgentCollaborationService(Manager()).communicate([
        {"sender": "planner_agent", "recipient": "code_agent", "content": "Use the approved plan."},
    ])
    assert result["success"] is True
    assert result["messages"][0]["content"] == "Use the approved plan."


def test_optimization_reports_outcomes_without_guessing_quality():
    result = AgentCollaborationService.optimize([
        {"agent": "planner_agent", "result": {"success": True}},
        {"agent": "planner_agent", "result": {"success": False}},
    ])
    assert result["success"] is True
    assert result["metrics"]["planner_agent"] == {"runs": 2, "successes": 1, "failures": 1}
    assert result["recommendations"][0]["recommendation"] == "investigate failures before increasing allocation"


def test_agent_collaboration_routes_integrate_with_the_real_service_boundary(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    calls = []

    def successful_run(self, agent_name, task):
        calls.append((agent_name, task))
        return {"success": True, "state": "completed", "agent": agent_name}

    monkeypatch.setattr("app.agents.agent_manager.AgentManager.run", successful_run)
    client = TestClient(app)
    response = client.post(
        "/agents/collaborate",
        json={"tasks": [
            {"agent": "planner_agent", "task": "Create a bounded plan"},
            {"agent": "code_agent", "task": "Implement the approved plan"},
        ]},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["state"] == "completed"
    assert calls == [
        ("planner_agent", "Create a bounded plan"),
        ("code_agent", "Implement the approved plan"),
    ]

    def failing_run(self, agent_name, task):
        return {"success": False, "state": "failed", "agent": agent_name}

    monkeypatch.setattr("app.agents.agent_manager.AgentManager.run", failing_run)
    failed = client.post(
        "/agents/collaborate",
        json={"tasks": [
            {"agent": "planner_agent", "task": "Create a bounded plan"},
            {"agent": "code_agent", "task": "Implement the approved plan"},
        ]},
    )
    assert failed.status_code == 200
    assert failed.json()["success"] is False
    assert failed.json()["code"] == "agent_failed"
    assert len(failed.json()["results"]) == 1


def test_agent_communication_and_self_evaluation_routes_cover_success_and_failure():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    communicated = client.post(
        "/agents/communicate",
        json={"messages": [
            {"sender": "planner_agent", "recipient": "code_agent", "content": "Use the approved plan."}
        ]},
    )
    assert communicated.status_code == 200
    assert communicated.json()["success"] is True
    assert communicated.json()["messages"][0]["content"] == "Use the approved plan."

    invalid_message = client.post(
        "/agents/communicate",
        json={"messages": [
            {"sender": "planner_agent", "recipient": "code_agent", "content": ""}
        ]},
    )
    assert invalid_message.status_code == 200
    assert invalid_message.json()["success"] is False
    assert invalid_message.json()["code"] == "invalid_message"

    evaluated = client.post(
        "/agents/evaluate",
        json={"results": [
            {"agent": "planner_agent", "result": {"success": True}},
            {"agent": "code_agent", "result": {"success": False}},
        ]},
    )
    assert evaluated.status_code == 200
    assert evaluated.json()["success"] is False
    assert evaluated.json()["accepted"] == 1
    assert evaluated.json()["rejected"] == 1


def test_agent_optimization_route_returns_measured_outcomes():
    from fastapi.testclient import TestClient
    from app.main import app

    response = TestClient(app).post(
        "/agents/optimize",
        json={"results": [
            {"agent": "planner_agent", "result": {"success": True}},
            {"agent": "planner_agent", "result": {"success": False}},
        ]},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["metrics"]["planner_agent"] == {
        "runs": 2, "successes": 1, "failures": 1
    }
    assert response.json()["recommendations"][0]["recommendation"] == (
        "investigate failures before increasing allocation"
    )
