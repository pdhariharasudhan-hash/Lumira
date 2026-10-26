from fastapi.testclient import TestClient

from app.main import app
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.providers.provider_registry import ProviderRegistry
from app.services.voice.transcript_service import TranscriptService


def test_voice_activation_and_playback_have_truthful_provider_boundaries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    upload = client.post(
        "/voice/upload",
        files={"audio": ("sample.wav", b"RIFF\x00\x00\x00\x00WAVE", "audio/wav")},
    )
    audio_id = upload.json()["data"]["artifact"]["artifact_id"]

    activation = client.post("/voice/activation", json={"artifact_id": audio_id})
    playback = client.post("/voice/playback", json={"text": "வணக்கம் Lumira", "language": "ta-en"})
    assert activation.status_code == 501
    assert activation.json()["detail"]["code"] == "provider_unavailable"
    assert playback.status_code == 501
    assert playback.json()["detail"]["code"] == "provider_unavailable"

    class WakeWord:
        def detect(self, audio_path):
            assert audio_path.endswith(".wav")
            return {"success": True, "detected": True}

    class Synthesis:
        def synthesize(self, text, language):
            assert (text, language) == ("வணக்கம் Lumira", "ta-en")
            return {"success": True, "content": b"RIFF\x00\x00\x00\x00WAVE", "extension": "wav"}

    ProviderRegistry.register("wake_word", WakeWord())
    ProviderRegistry.register("speech_synthesis", Synthesis())
    try:
        activated = client.post("/voice/activation", json={"artifact_id": audio_id})
        spoken = client.post("/voice/playback", json={"text": "வணக்கம் Lumira", "language": "ta-en"})
    finally:
        ProviderRegistry.clear()

    assert activated.json()["activated"] is True
    assert spoken.json()["success"] is True
    assert ArtifactManagerService().get_artifact(spoken.json()["artifact"]["artifact_id"])["type"] == "audio"


def test_transcript_provider_registry_persists_transcript_and_detects_tamil_english(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    audio = ArtifactManagerService().create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )

    class Transcription:
        def transcribe(self, audio_path):
            return "வணக்கம் Lumira, create a report"

    ProviderRegistry.register("transcription", Transcription())
    try:
        result = TranscriptService().generate_transcript(audio["artifact_id"])
    finally:
        ProviderRegistry.clear()

    assert result["success"] is True
    assert result["transcript_text"] == "வணக்கம் Lumira, create a report"
    assert result["language"] == "ta-en"
    assert result["language_confidence"] > 0
    transcript = ArtifactManagerService().get_artifact(result["transcript_artifact"]["artifact_id"])
    assert transcript["type"] == "transcripts"


def test_transcription_validates_only_audio_header_not_entire_recording(tmp_path, monkeypatch):
    from pathlib import Path

    monkeypatch.chdir(tmp_path)
    audio = ArtifactManagerService().create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE" + (b"x" * 4096), "voice_capture", "wav"
    )

    class Transcription:
        def transcribe(self, audio_path):
            assert Path(audio_path).is_file()
            return "header-only validation works"

    def reject_full_file_read(self, *args, **kwargs):
        raise AssertionError("transcription validation must not load the whole audio file")

    monkeypatch.setattr(Path, "read_bytes", reject_full_file_read)
    result = TranscriptService(provider=Transcription()).generate_transcript(audio["artifact_id"])

    assert result["success"] is True
    assert result["language"] in {"en", "ta-en"}


def test_voice_result_is_persisted_to_session_from_stored_artifacts(tmp_path, monkeypatch):
    from app.services.sessions.session_manager_service import SessionManagerService

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    session = SessionManagerService().create_session()
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )
    transcript = artifacts.create_artifact(
        "transcripts", "Transcript text that must survive refresh.", audio["artifact_id"], "txt"
    )
    summary = artifacts.create_artifact(
        "summaries", "Summary text that must survive refresh.", transcript["artifact_id"], "txt"
    )

    response = client.post(
        f"/sessions/{session['session_id']}/voice-result",
        json={
            "audio_artifact_id": audio["artifact_id"],
            "transcript_artifact_id": transcript["artifact_id"],
            "summary_artifact_id": summary["artifact_id"],
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    restored = SessionManagerService().get_session(session["session_id"])
    message = restored["recent_messages"][-1]
    assert message["role"] == "assistant"
    assert "Transcript text that must survive refresh." in message["content"]
    assert "Summary text that must survive refresh." in message["content"]
    assert message["metadata"]["voice_capture"]["audio_artifact_id"] == audio["artifact_id"]


def test_voice_result_rejects_transcript_from_another_audio_artifact(tmp_path, monkeypatch):
    from app.services.sessions.session_manager_service import SessionManagerService

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    session = SessionManagerService().create_session()
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )
    unrelated_audio = artifacts.create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )
    transcript = artifacts.create_artifact(
        "transcripts", "Unrelated transcript.", unrelated_audio["artifact_id"], "txt"
    )

    response = client.post(
        f"/sessions/{session['session_id']}/voice-result",
        json={"audio_artifact_id": audio["artifact_id"], "transcript_artifact_id": transcript["artifact_id"]},
    )

    assert response.status_code == 409
    assert "does not belong" in response.json()["detail"]


def test_voice_result_persists_provider_unavailability_when_only_audio_exists(tmp_path, monkeypatch):
    from app.services.sessions.session_manager_service import SessionManagerService

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    session = SessionManagerService().create_session()
    audio = ArtifactManagerService().create_binary_artifact(
        "audio", b"RIFF\x00\x00\x00\x00WAVE", "voice_capture", "wav"
    )

    response = client.post(
        f"/sessions/{session['session_id']}/voice-result",
        json={"audio_artifact_id": audio["artifact_id"]},
    )

    assert response.status_code == 200
    message = SessionManagerService().get_session(session["session_id"])["recent_messages"][-1]
    assert "Transcription unavailable or not configured." in message["content"]
