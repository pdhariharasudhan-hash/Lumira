from app.services.recovery.recovery_checkpoint_service import RecoveryCheckpointService

def test_checkpoint_summary_counts_stages(tmp_path):
    service = RecoveryCheckpointService(tmp_path / "checkpoints.json")
    service.save("one", "active", {})
    service.save("two", "active", {})
    summary = service.summary()
    assert summary["total"] == 2
    assert summary["stages"]["active"] == 2
    assert summary["latest"]["workflow_id"] == "two"
