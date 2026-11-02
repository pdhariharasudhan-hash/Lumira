from app.services.voice.audio_playback_service import AudioPlaybackService


class FakeArtifacts:
    def get_artifact(self, artifact_id):
        return {"artifact_id": artifact_id, "type": "audio"} if artifact_id == "audio-1" else None

    def get_artifact_path(self, artifact_id):
        return None


def test_audio_playback_rejects_blank_artifact():
    result = AudioPlaybackService(FakeArtifacts()).resolve("")
    assert result["success"] is False


def test_audio_playback_reports_unavailable_audio():
    result = AudioPlaybackService(FakeArtifacts()).resolve("audio-1")
    assert result["code"] == "audio_unavailable"


def test_audio_resolver_rejects_blank_identifier():
    result = AudioPlaybackService(FakeArtifacts()).resolve("")
    assert result["code"] == "invalid_audio_artifact"
