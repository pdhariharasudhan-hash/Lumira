from app.services.workflow_recovery.run_recovery_service import RunRecoveryService


def test_recovery_run_preserves_core_context(tmp_path):
    service = RunRecoveryService(tmp_path / "runs.json")
    context = {"success": True, "context": {"session_id": "s1"}}
    run = service.create_run(
        "test goal",
        {"steps": ["inspect"]},
        "s1",
        core_context=context,
    )
    assert run["core_context"]["context"]["session_id"] == "s1"


def test_recovery_window_inherits_core_context(tmp_path):
    service = RunRecoveryService(tmp_path / "runs.json")
    context = {"success": True, "operation": "workflow"}
    run = service.create_run(
        "test goal",
        {"steps": ["inspect"]},
        core_context=context,
    )
    child = service.create_recovery_window(run["run_id"])
    assert child["core_context"] == context
