from app.services.artifacts.artifact_manager_service import ArtifactManagerService


def test_artifact_content_integrity_detects_missing_and_corrupt_files(tmp_path):
    manager = ArtifactManagerService(
        tmp_path / "artifacts",
        tmp_path / "memory" / "artifact_index.json",
    )
    record = manager.create_artifact("summaries", "verified content", "test")

    assert manager.verify_artifact_content(record["artifact_id"])["success"] is True
    path = manager.get_artifact_path(record["artifact_id"])
    path.write_text("changed content", encoding="utf-8")
    assert manager.verify_artifact_content(record["artifact_id"])["code"] == "artifact_content_corrupt"

    path.unlink()
    assert manager.verify_artifact_content(record["artifact_id"])["code"] == "artifact_content_missing"


def test_artifact_integrity_metadata_is_persisted_for_binary_content(tmp_path):
    manager = ArtifactManagerService(
        tmp_path / "artifacts",
        tmp_path / "memory" / "artifact_index.json",
    )
    record = manager.create_binary_artifact(
        "audio",
        b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 4,
        "test",
        "wav",
    )

    assert len(record["content_sha256"]) == 64
    assert record["content_bytes"] == 16
    assert manager.verify_artifact_content(record["artifact_id"])["success"] is True
