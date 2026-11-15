from app.services.brain import workflow_execution_gate


def test_workflow_execution_gate_requires_explicit_boolean_approval(monkeypatch):
    class Brain:
        def understand(self, goal, **kwargs):
            return {
                "success": True,
                "state": {"verification_result": {"ready_for_execution": "true"}},
            }

    monkeypatch.setattr(workflow_execution_gate, "LumiraCore", Brain)

    result = workflow_execution_gate.preflight_workflow_execution("Build the project")

    assert result["allowed"] is False
    assert result["code"] == "brain_verification_rejected"


def test_workflow_execution_gate_fails_closed_and_sanitizes_brain_errors(monkeypatch):
    class Brain:
        def understand(self, goal, **kwargs):
            raise RuntimeError("provider-secret-detail")

    monkeypatch.setattr(workflow_execution_gate, "LumiraCore", Brain)

    result = workflow_execution_gate.preflight_workflow_execution("Continue safely")

    assert result["allowed"] is False
    assert result["code"] == "brain_preflight_failed"
    assert "provider-secret-detail" not in str(result)


def test_workflow_execution_gate_forwards_context_and_approves_only_verified_requests(monkeypatch):
    calls = []

    class Brain:
        def understand(self, goal, **kwargs):
            calls.append((goal, kwargs))
            return {
                "success": True,
                "state": {"verification_result": {"ready_for_execution": True}},
            }

    monkeypatch.setattr(workflow_execution_gate, "LumiraCore", Brain)

    result = workflow_execution_gate.preflight_workflow_execution(
        "Resume the approved workflow",
        session_id="session-1",
        project_id="project-1",
        workspace="workspace-1",
        source="workflow_resume",
        run_id="run-1",
    )

    assert result == {"allowed": True}
    assert calls == [
        (
            "Resume the approved workflow",
            {
                "session_id": "session-1",
                "project": "project-1",
                "workspace": "workspace-1",
                "metadata": {"source": "workflow_resume", "workflow_run_id": "run-1"},
            },
        )
    ]


def test_workflow_resume_callback_rejection_prevents_resume_and_stage_execution(tmp_path, monkeypatch):
    from app.agents.workflow_engine import WorkflowEngine
    from app.services.workflow_recovery.run_recovery_service import RunRecoveryService

    monkeypatch.chdir(tmp_path)
    recovery = RunRecoveryService()
    run = recovery.create_run(
        "Continue the project safely",
        {"success": True, "steps": ["search"]},
    )

    class MustNotExecuteRouter:
        def execute_step(self, step, goal, context):
            raise AssertionError("a rejected resume must not execute a stage")

    seen = []

    def reject_resume(record):
        seen.append(record)
        return {
            "allowed": False,
            "state": "rejected",
            "code": "brain_verification_rejected",
            "message": "Resume was not approved.",
        }

    result = WorkflowEngine(
        planner=object(),
        router=MustNotExecuteRouter(),
        recovery=recovery,
    ).resume(run["run_id"], before_resume=reject_resume)

    assert result["success"] is False
    assert result["code"] == "brain_verification_rejected"
    assert seen[0]["goal"] == "Continue the project safely"
    assert recovery.get_run(run["run_id"])["resume_count"] == 0


def test_workflow_resume_malformed_gate_response_fails_closed(tmp_path, monkeypatch):
    from app.agents.workflow_engine import WorkflowEngine
    from app.services.workflow_recovery.run_recovery_service import RunRecoveryService

    monkeypatch.chdir(tmp_path)
    recovery = RunRecoveryService()
    run = recovery.create_run(
        "Continue the project safely",
        {"success": True, "steps": ["search"]},
    )

    result = WorkflowEngine(
        planner=object(),
        router=object(),
        recovery=recovery,
    ).resume(
        run["run_id"],
        before_resume=lambda _: {"allowed": False, "state": []},
    )

    assert result["success"] is False
    assert result["state"] == "blocked"
    assert result["code"] == "resume_preflight_rejected"
    assert recovery.get_run(run["run_id"])["resume_count"] == 0
