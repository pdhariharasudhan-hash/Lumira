from app.routes import run as run_route
from app.schemas.common import GenericInput


def test_run_pipeline_rejects_brain_verification_before_workflow_execution(monkeypatch):
    workflow_calls = []

    class BrainCore:
        def understand(self, request, **kwargs):
            return {
                "success": True,
                "state": {
                    "verification_result": {
                        "ready_for_execution": False,
                        "failed_checks": ["ambiguous_goal"],
                    }
                },
            }

    class Workflow:
        def execute(self, *args, **kwargs):
            workflow_calls.append((args, kwargs))
            return {"success": True, "state": "completed"}

    monkeypatch.setattr(run_route, "LumiraCore", BrainCore, raising=False)
    monkeypatch.setattr(run_route, "WorkflowEngine", Workflow)

    response = run_route.run_pipeline(GenericInput(input="Build something"))

    assert response["success"] is False
    assert response["endpoint"] == "run"
    assert response["status"] == "rejected"
    assert response["data"]["code"] == "brain_verification_rejected"
    assert workflow_calls == []


def test_run_pipeline_requires_explicit_boolean_brain_approval(monkeypatch):
    workflow_calls = []

    class BrainCore:
        def understand(self, request, **kwargs):
            return {
                "success": True,
                "state": {
                    "verification_result": {"ready_for_execution": "true"}
                },
            }

    class Workflow:
        def execute(self, *args, **kwargs):
            workflow_calls.append((args, kwargs))
            return {"success": True, "state": "completed"}

    monkeypatch.setattr(run_route, "LumiraCore", BrainCore, raising=False)
    monkeypatch.setattr(run_route, "WorkflowEngine", Workflow)

    response = run_route.run_pipeline(GenericInput(input="Build something"))

    assert response["success"] is False
    assert response["data"]["code"] == "brain_verification_rejected"
    assert workflow_calls == []


def test_run_pipeline_preserves_workflow_response_after_brain_approval(monkeypatch):
    workflow_calls = []
    workflow_result = {"success": True, "state": "completed", "run_id": "run-1"}

    class BrainCore:
        def understand(self, request, **kwargs):
            assert request == "Search the project"
            assert kwargs == {
                "session_id": "session-1",
                "project": "project-1",
                "workspace": "workspace-1",
                "metadata": {"source": "workflow_run"},
            }
            return {
                "success": True,
                "state": {
                    "verification_result": {"ready_for_execution": True}
                },
            }

    class Workflow:
        def execute(self, *args, **kwargs):
            workflow_calls.append((args, kwargs))
            return workflow_result

    monkeypatch.setattr(run_route, "LumiraCore", BrainCore, raising=False)
    monkeypatch.setattr(run_route, "WorkflowEngine", Workflow)

    response = run_route.run_pipeline(
        GenericInput(
            input="Search the project",
            session_id="session-1",
            workspace_id="workspace-1",
            project_id="project-1",
        )
    )

    assert response == {
        "success": True,
        "endpoint": "run",
        "status": "ok",
        "data": workflow_result,
    }
    assert workflow_calls == [(
        ("Search the project",),
        {"session_id": "session-1", "project_id": "project-1"},
    )]


def test_run_pipeline_fails_closed_when_brain_does_not_return_verification(monkeypatch):
    workflow_calls = []

    class BrainCore:
        def understand(self, request, **kwargs):
            return {"success": True, "state": {}}

    class Workflow:
        def execute(self, *args, **kwargs):
            workflow_calls.append((args, kwargs))
            return {"success": True, "state": "completed"}

    monkeypatch.setattr(run_route, "LumiraCore", BrainCore, raising=False)
    monkeypatch.setattr(run_route, "WorkflowEngine", Workflow)

    response = run_route.run_pipeline(GenericInput(input="Build something"))

    assert response["success"] is False
    assert response["data"]["code"] == "brain_verification_rejected"
    assert workflow_calls == []


def test_run_pipeline_fails_closed_when_brain_preflight_raises(monkeypatch):
    workflow_calls = []

    class BrainCore:
        def understand(self, request, **kwargs):
            raise RuntimeError("sensitive provider detail")

    class Workflow:
        def execute(self, *args, **kwargs):
            workflow_calls.append((args, kwargs))
            return {"success": True, "state": "completed"}

    monkeypatch.setattr(run_route, "LumiraCore", BrainCore)
    monkeypatch.setattr(run_route, "WorkflowEngine", Workflow)

    response = run_route.run_pipeline(GenericInput(input="Build something"))

    assert response["success"] is False
    assert response["data"]["code"] == "brain_preflight_failed"
    assert "sensitive provider detail" not in str(response)
    assert workflow_calls == []


def test_core_understand_forwards_workspace_to_brain_request(monkeypatch):
    from types import SimpleNamespace

    from app.core.lumira_core import LumiraCore
    from app.services.brain import brain_service

    requests = []

    class State:
        def model_dump(self, mode):
            return {"verification_result": {"ready_for_execution": True}}

    class Brain:
        def execute(self, request):
            requests.append(request)
            return SimpleNamespace(success=True, state=State(), trace=[], error=None)

    monkeypatch.setattr(brain_service, "BrainService", Brain)
    core = LumiraCore.__new__(LumiraCore)
    monkeypatch.setattr(core, "core_context", lambda **kwargs: {"context": {}})

    result = core.understand(
        "Search the project",
        session_id="session-1",
        project="project-1",
        workspace="workspace-1",
    )

    assert result["success"] is True
    assert requests[0].workspace == "workspace-1"
    assert requests[0].project == "project-1"
    assert requests[0].session_id == "session-1"


def test_run_resume_requires_brain_approval_before_workflow_resume(monkeypatch):
    class BrainCore:
        def understand(self, request, **kwargs):
            assert request == "Resume a saved workflow"
            assert kwargs["metadata"] == {
                "source": "workflow_resume",
                "workflow_run_id": "run-1",
            }
            return {
                "success": True,
                "state": {
                    "verification_result": {"ready_for_execution": False}
                },
            }

    class Workflow:
        def resume(self, run_id, *, before_resume):
            assert run_id == "run-1"
            approval = before_resume(
                {"goal": "Resume a saved workflow", "session_id": "session-1"}
            )
            return {
                "success": False,
                "state": approval["state"],
                "code": approval["code"],
                "message": approval["message"],
            }

    monkeypatch.setattr(run_route, "LumiraCore", BrainCore)
    monkeypatch.setattr(run_route, "WorkflowEngine", Workflow)

    response = run_route.resume_run("run-1")

    assert response["success"] is False
    assert response["code"] == "brain_verification_rejected"


def test_recovery_resume_requires_brain_approval_before_workflow_resume(monkeypatch):
    from app.routes import recovery as recovery_route

    class BrainCore:
        def understand(self, request, **kwargs):
            assert request == "Resume a saved workflow"
            assert kwargs["metadata"] == {
                "source": "workflow_recovery_resume",
                "workflow_run_id": "run-2",
            }
            return {
                "success": True,
                "state": {
                    "verification_result": {"ready_for_execution": False}
                },
            }

    class Recovery:
        def get_run(self, run_id):
            assert run_id == "run-2"
            return {"run_id": run_id}

    class Workflow:
        def __init__(self, recovery):
            assert isinstance(recovery, Recovery)

        def resume(self, run_id, *, before_resume):
            approval = before_resume(
                {"goal": "Resume a saved workflow", "session_id": "session-2"}
            )
            return {
                "success": False,
                "state": approval["state"],
                "code": approval["code"],
                "message": approval["message"],
            }

    monkeypatch.setattr(recovery_route, "LumiraCore", BrainCore)
    monkeypatch.setattr(recovery_route, "RunRecoveryService", Recovery)
    monkeypatch.setattr(recovery_route, "WorkflowEngine", Workflow)

    response = recovery_route.resume_recovery_run("run-2")

    assert response["success"] is False
    assert response["code"] == "brain_verification_rejected"


def test_run_pipeline_stops_when_brain_rejects_request(monkeypatch):
    workflow_calls = []

    class BrainCore:
        def understand(self, request, **kwargs):
            return {"success": False, "state": None, "error": "rejected"}

    class Workflow:
        def execute(self, *args, **kwargs):
            workflow_calls.append((args, kwargs))
            return {"success": True, "state": "completed"}

    monkeypatch.setattr(run_route, "LumiraCore", BrainCore, raising=False)
    monkeypatch.setattr(run_route, "WorkflowEngine", Workflow)

    response = run_route.run_pipeline(GenericInput(input="Build something"))

    assert response["success"] is False
    assert response["data"]["code"] == "brain_preflight_failed"
    assert workflow_calls == []
