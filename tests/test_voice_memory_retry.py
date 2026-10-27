from fastapi import HTTPException
import pytest
from app.routes import voice_capture


def test_retry_voice_memory_restores_memory_from_saved_artifacts(tmp_path, monkeypatch):
    audio_id, transcript_id, summary_id = "audio-1", "transcript-1", "summary-1"
    transcript_path = tmp_path / "transcript.txt"; transcript_path.write_text("Build a small robot", encoding="utf-8")
    summary_path = tmp_path / "summary.txt"; summary_path.write_text("Idea: build a small robot", encoding="utf-8")
    records = {audio_id: {"artifact_id": audio_id, "type": "audio", "source": "voice_capture"}, transcript_id: {"artifact_id": transcript_id, "type": "transcripts", "source": audio_id}, summary_id: {"artifact_id": summary_id, "type": "summaries", "source": transcript_id}}
    paths = {transcript_id: transcript_path, summary_id: summary_path}
    class FakeArtifacts:
        MAX_CONTENT_LENGTH = 10000
        def get_artifact(self, artifact_id): return records.get(artifact_id)
        def get_artifact_path(self, artifact_id): return paths.get(artifact_id)
    saved = {}
    class FakeMemory:
        def get_all(self): return {"experiences": []}
        def record_experience(self, **kwargs):
            saved.update(kwargs); return {"experience_id": "experience-1"}
    monkeypatch.setattr("app.services.artifacts.artifact_manager_service.ArtifactManagerService", FakeArtifacts)
    monkeypatch.setattr(voice_capture, "MemoryService", FakeMemory)
    result = voice_capture.retry_voice_memory(voice_capture.VoiceMemoryRetryRequest(audio_artifact_id=audio_id, transcript_artifact_id=transcript_id, summary_artifact_id=summary_id))
    assert result["success"] is True and result["state"] == "saved"
    assert result["experience_id"] == "experience-1"
    assert saved["summary"] == "Idea: build a small robot"
    assert saved["artifact_ids"] == [audio_id, transcript_id, summary_id]
    assert saved["verified"] is False


def test_retry_voice_memory_rejects_transcript_from_another_capture(monkeypatch):
    class FakeArtifacts:
        MAX_CONTENT_LENGTH = 10000
        def get_artifact(self, artifact_id):
            if artifact_id == "audio-1": return {"artifact_id": "audio-1", "type": "audio"}
            return {"artifact_id": "transcript-1", "type": "transcripts", "source": "different-audio"}
        def get_artifact_path(self, artifact_id): return None
    monkeypatch.setattr("app.services.artifacts.artifact_manager_service.ArtifactManagerService", FakeArtifacts)
    with pytest.raises(HTTPException) as error:
        voice_capture.retry_voice_memory(voice_capture.VoiceMemoryRetryRequest(audio_artifact_id="audio-1", transcript_artifact_id="transcript-1"))
    assert error.value.status_code == 409
