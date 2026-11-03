from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.voice.voice_history_service import VoiceHistoryService


def test_voice_history_lists_artifacts_from_current_manager(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = ArtifactManagerService("artifacts", "memory/artifact_index.json")
    audio = artifacts.create_binary_artifact(
        "audio",
        b"ID3\x04\x00\x00\x00\x00\x00\x00",
        "voice_capture",
        "mp3",
    )
    transcript = artifacts.create_artifact(
        "transcripts", "captured words", audio["artifact_id"]
    )
    summary = artifacts.create_artifact(
        "summaries", "short summary", transcript["artifact_id"]
    )
    artifacts.create_artifact("reports", "unrelated report", "manual")

    history = VoiceHistoryService(artifacts).list()

    assert [item["artifact_id"] for item in history] == [
        summary["artifact_id"],
        transcript["artifact_id"],
        audio["artifact_id"],
    ]


def test_voice_history_respects_limit_and_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = ArtifactManagerService("artifacts", "memory/artifact_index.json")
    artifacts.create_artifact("transcripts", "one", "voice_capture")
    artifacts.create_artifact("summaries", "two", "voice_capture")

    history = VoiceHistoryService(artifacts)
    assert len(history.list(limit=1)) == 1
    assert history.list(limit=0) == []
