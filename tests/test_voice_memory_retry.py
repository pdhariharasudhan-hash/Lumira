from fastapi.testclient import TestClient

from app.main import app
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.memory.memory_service import MemoryService


def _voice_artifacts():
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )
    transcript = artifacts.create_artifact(
        "transcripts",
        "வணக்கம் Lumira, create a project plan.",
        audio["artifact_id"],
        "txt",
    )
    summary = artifacts.create_artifact(
        "summaries",
        "The user requested a project plan.",
        transcript["artifact_id"],
        "txt",
    )
    return artifacts, audio, transcript, summary


def test_retry_voice_memory_persists_saved_audio_transcript_and_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts, audio, transcript, summary = _voice_artifacts()

    response = client.post(
        "/voice/retry-memory",
        json={
            "audio_artifact_id": audio["artifact_id"],
            "transcript_artifact_id": transcript["artifact_id"],
            "summary_artifact_id": summary["artifact_id"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["memory"]["state"] == "saved"
    assert payload["artifact_relationships"]
    experiences = MemoryService().get_all()["experiences"]
    experience = next(item for item in experiences if audio["artifact_id"] in item["artifact_ids"])
    assert transcript["artifact_id"] in experience["artifact_ids"]
    assert summary["artifact_id"] in experience["artifact_ids"]
    assert experience["verified"] is False
    assert any(
        link["artifact_id"] == transcript["artifact_id"] and link["relation"] == "transcribed_as"
        for link in artifacts.get_artifact_links(audio["artifact_id"])["links"]
    )


def test_retry_voice_memory_attaches_missing_artifacts_to_existing_experience(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    _, audio, transcript, summary = _voice_artifacts()
    memory = MemoryService()
    existing = memory.record_experience(
        experience_type="workflow",
        summary="Existing voice capture",
        outcome="Captured audio, memory links need repair",
        artifact_ids=[audio["artifact_id"]],
        lessons=[],
        verified=False,
    )

    response = client.post(
        "/voice/retry-memory",
        json={
            "audio_artifact_id": audio["artifact_id"],
            "transcript_artifact_id": transcript["artifact_id"],
            "summary_artifact_id": summary["artifact_id"],
        },
    )

    assert response.status_code == 200
    assert response.json()["memory"]["state"] == "updated"
    updated = next(
        item for item in MemoryService().get_all()["experiences"]
        if item["experience_id"] == existing["experience_id"]
    )
    assert updated["artifact_ids"] == [
        audio["artifact_id"],
        transcript["artifact_id"],
        summary["artifact_id"],
    ]


def test_retry_voice_memory_rejects_unrelated_transcript(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts, audio, transcript, _ = _voice_artifacts()
    other_audio = artifacts.create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "other_capture", "wav"
    )
    unrelated = artifacts.create_artifact(
        "transcripts", "Unrelated transcript content.", other_audio["artifact_id"], "txt"
    )

    response = client.post(
        "/voice/retry-memory",
        json={
            "audio_artifact_id": audio["artifact_id"],
            "transcript_artifact_id": unrelated["artifact_id"],
            "summary_artifact_id": None,
        },
    )

    assert response.status_code == 409
    assert "does not belong" in response.json()["detail"]



def test_retry_voice_memory_rejects_archived_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    artifacts, audio, transcript, summary = _voice_artifacts()
    assert artifacts.archive_artifact(transcript["artifact_id"]) is True

    response = client.post(
        "/voice/retry-memory",
        json={
            "audio_artifact_id": audio["artifact_id"],
            "transcript_artifact_id": transcript["artifact_id"],
            "summary_artifact_id": summary["artifact_id"],
        },
    )

    assert response.status_code == 409
    assert "archived" in response.json()["detail"]
