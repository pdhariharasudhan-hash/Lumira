from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.voice.transcript_service import TranscriptService


class NeverTranscribe:
    calls = 0

    def transcribe(self, audio_path):
        self.calls += 1
        raise AssertionError("existing transcript should be reused")


def _service(tmp_path):
    artifacts = ArtifactManagerService(
        tmp_path / "artifacts",
        tmp_path / "memory" / "artifact_index.json",
    )
    audio = artifacts.create_binary_artifact(
        "audio",
        b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 4,
        "voice-capture",
        "wav",
    )
    provider = NeverTranscribe()
    service = TranscriptService(provider=provider)
    service.artifacts = artifacts
    return service, artifacts, audio, provider


def test_existing_transcript_is_reused_without_calling_provider(tmp_path):
    service, artifacts, audio, provider = _service(tmp_path)
    transcript = artifacts.create_artifact(
        "transcripts",
        "Turn left at the next street.",
        audio["artifact_id"],
    )

    result = service.generate_transcript(audio["artifact_id"])

    assert result["success"] is True
    assert result["reused"] is True
    assert result["transcript_artifact"]["artifact_id"] == transcript["artifact_id"]
    assert result["transcript_text"] == "Turn left at the next street."
    assert provider.calls == 0
    assert len([
        item for item in artifacts.get_all_artifacts()
        if item["type"] == "transcripts" and item["source"] == audio["artifact_id"]
    ]) == 1


def test_corrupt_existing_transcript_fails_closed_without_replacement(tmp_path):
    service, artifacts, audio, provider = _service(tmp_path)
    transcript = artifacts.create_artifact(
        "transcripts",
        "Original transcript.",
        audio["artifact_id"],
    )
    artifacts.get_artifact_path(transcript["artifact_id"]).write_text(
        "tampered transcript",
        encoding="utf-8",
    )

    result = service.generate_transcript(audio["artifact_id"])

    assert result["success"] is False
    assert result["code"] == "artifact_content_corrupt"
    assert provider.calls == 0
    assert len([
        item for item in artifacts.get_all_artifacts()
        if item["type"] == "transcripts" and item["source"] == audio["artifact_id"]
    ]) == 1


def test_archived_transcript_is_not_reused(tmp_path):
    service, artifacts, audio, provider = _service(tmp_path)
    old = artifacts.create_artifact(
        "transcripts",
        "Archived transcript.",
        audio["artifact_id"],
    )
    assert artifacts.archive_artifact(old["artifact_id"]) is True

    result = service.generate_transcript(audio["artifact_id"])

    assert result["success"] is False
    assert result["code"] == "external_provider_consent_required"
    assert provider.calls == 0
    assert result.get("reused") is not True
