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
    assert result["language"] == "ta-en"
    assert result["language_confidence"] > 0
    transcript = ArtifactManagerService().get_artifact(result["transcript_artifact"]["artifact_id"])
    assert transcript["type"] == "transcripts"
