from app.services.providers.faster_whisper_transcription_provider import FasterWhisperTranscriptionProvider
from app.services.providers.openai_compatible_transcription_provider import OpenAICompatibleTranscriptionProvider
from app.services.voice.transcript_service import TranscriptService


class FakeArtifacts:
    MAX_BINARY_CONTENT_BYTES = 25_000_000
    BINARY_FORMATS = {"audio": {"wav", "mp3", "m4a", "ogg", "webm"}}

    def __init__(self, path):
        self.path = path

    def get_artifact(self, artifact_id):
        return {"artifact_id": artifact_id, "type": "audio"}

    def get_artifact_path(self, artifact_id):
        return self.path

    @staticmethod
    def _has_binary_signature(artifact_type, signature, extension):
        return True


class FakeProvider:
    SUPPORTED_EXTENSIONS = {"wav", "mp3"}

    def __init__(self):
        self.called = False

    def transcribe(self, path):
        self.called = True
        return "should not be called"


class FakePolicy:
    def authorize(self, provider, operation):
        return None


def test_local_transcription_supports_all_stored_audio_formats():
    assert FasterWhisperTranscriptionProvider.SUPPORTED_EXTENSIONS == {
        "wav", "mp3", "m4a", "ogg", "webm"
    }


def test_external_transcription_supports_webm_with_correct_mime_type():
    assert "webm" in OpenAICompatibleTranscriptionProvider.SUPPORTED_EXTENSIONS
    assert OpenAICompatibleTranscriptionProvider._content_type("webm") == "video/webm"
    assert "ogg" not in OpenAICompatibleTranscriptionProvider.SUPPORTED_EXTENSIONS


def test_transcript_service_reports_provider_format_mismatch_before_call(tmp_path):
    audio = tmp_path / "capture.ogg"
    audio.write_bytes(b"OggS" + b"0" * 16)
    provider = FakeProvider()
    service = object.__new__(TranscriptService)
    service.artifacts = FakeArtifacts(audio)
    service.provider = provider
    service.provider_policy = FakePolicy()

    result = service.generate_transcript("audio-1")

    assert result["success"] is False
    assert result["code"] == "unsupported_audio_format"
    assert result["format"] == "ogg"
    assert result["supported_formats"] == ["mp3", "wav"]
    assert provider.called is False
