from app.services.recovery.recovery_checkpoint_service import RecoveryCheckpointService


def test_checkpoint_replaces_same_workflow(tmp_path):
    service = RecoveryCheckpointService(tmp_path / "checkpoints.json")
    service.save("workflow-1", "active", {"step": 1})
    service.save("workflow-1", "completed", {"step": 2})
    checkpoint = service.resume("workflow-1")
    assert checkpoint["stage"] == "completed"
    assert checkpoint["state"]["step"] == 2


def test_missing_checkpoint_returns_none(tmp_path):
    assert RecoveryCheckpointService(tmp_path / "checkpoints.json").resume("missing") is None


def test_checkpoint_list_and_discard(tmp_path):
    service = RecoveryCheckpointService(tmp_path / "checkpoints.json")
    service.save("workflow-1", "active", {"step": 1})
    assert service.list_recent(10)[0]["workflow_id"] == "workflow-1"
    assert service.discard("workflow-1") is True
    assert service.resume("workflow-1") is None
