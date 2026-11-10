import pytest

from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.image.image_generation_service import ImageGenerationService
from app.services.response.summary_service import SummaryService
from app.services.voice.transcript_service import TranscriptService
from app.services.resources.resource_budget_service import ResourceBudgetService


@pytest.fixture(autouse=True)
def normal_resource_budget(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {"defer_optional_heavy_media_work": False, "resource_pressure": "normal"},
    )


class RaisingImageProvider:
    provider_scope = "local"
    def generate(self, prompt, image_type):
        raise RuntimeError("provider credentials leaked")


class InvalidImageProvider:
    provider_scope = "local"
    def generate(self, prompt, image_type):
        return {"success": True, "content": b"not an image", "extension": "png"}


class RaisingInvalidImageProvider:
    provider_scope = "local"
    def generate(self, prompt, image_type):
        raise ValueError("private provider endpoint details")


class ValidImageProvider:
    provider_scope = "local"
    def generate(self, prompt, image_type):
        return {"success": True, "content": b"\x89PNG\r\n\x1a\nimage", "extension": "png"}


class RaisingTranscriptionProvider:
    provider_scope = "local"
    def transcribe(self, audio_path):
        raise RuntimeError("provider credentials leaked")


class RaisingSummaryProvider:
    provider_scope = "local"
    def summarize(self, transcript):
        raise RuntimeError("provider credentials leaked")


class ValidTranscriptionProvider:
    provider_scope = "local"
    def transcribe(self, audio_path):
        assert audio_path.endswith(".wav")
        return "A verified local transcript."


class ValidSummaryProvider:
    provider_scope = "local"
    def summarize(self, transcript):
        return f"Summary: {transcript}"


class FlakyTranscriptionProvider:
    provider_scope = "local"

    def __init__(self):
        self.calls = 0

    def transcribe(self, audio_path):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary provider failure")
        return "Recovered transcript."


class FlakySummaryProvider:
    provider_scope = "local"

    def __init__(self):
        self.calls = 0

    def summarize(self, transcript):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary provider failure")
        return "Recovered summary."


def create_test_audio(artifacts):
    return artifacts.create_binary_artifact("audio", b"RIFF\x00\x00\x00\x00WAVE", "test", "wav")


def test_image_provider_errors_do_not_create_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    failed = ImageGenerationService(RaisingImageProvider()).generate("diagram")
    assert failed["code"] == "provider_error"
    assert "provider credentials leaked" not in str(failed)

    invalid = ImageGenerationService(InvalidImageProvider()).generate("diagram")
    assert invalid["code"] == "invalid_provider_response"

    invalid_exception = ImageGenerationService(RaisingInvalidImageProvider()).generate("diagram")
    assert invalid_exception["code"] == "invalid_provider_response"
    assert "private provider endpoint details" not in str(invalid_exception)
    assert ArtifactManagerService().get_all_artifacts() == []


def test_valid_image_provider_output_flows_through_artifact_manager(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = ImageGenerationService(ValidImageProvider()).generate("diagram")

    assert result["success"] is True
    artifact = ArtifactManagerService().get_artifact(result["artifact"]["artifact_id"])
    assert artifact["type"] == "images"
    assert open(artifact["file"], "rb").read().startswith(b"\x89PNG\r\n\x1a\n")


def test_voice_provider_errors_return_structured_results_without_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = ArtifactManagerService()
    audio = create_test_audio(artifacts)
    transcript_result = TranscriptService(RaisingTranscriptionProvider()).generate_transcript(audio["artifact_id"])
    assert transcript_result["code"] == "provider_error"
    assert "provider credentials leaked" not in str(transcript_result)
    assert artifacts.search("transcripts") == []

    transcript = artifacts.create_artifact("transcripts", "A transcript.", audio["artifact_id"], "txt")
    summary_result = SummaryService(RaisingSummaryProvider()).generate_summary(transcript["artifact_id"])
    assert summary_result["code"] == "provider_error"
    assert "provider credentials leaked" not in str(summary_result)
    assert artifacts.search("summaries") == []


def test_voice_providers_unavailable_are_explicit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = ArtifactManagerService()
    audio = create_test_audio(artifacts)
    assert TranscriptService().generate_transcript(audio["artifact_id"])["code"] == "provider_unavailable"
    transcript = artifacts.create_artifact("transcripts", "A transcript.", audio["artifact_id"], "txt")
    assert SummaryService().generate_summary(transcript["artifact_id"])["code"] == "provider_unavailable"


def test_voice_provider_outputs_are_persisted_through_artifact_manager(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = ArtifactManagerService()
    audio = create_test_audio(artifacts)

    transcription = TranscriptService(ValidTranscriptionProvider()).generate_transcript(audio["artifact_id"])
    assert transcription["success"] is True
    transcript = artifacts.get_artifact(transcription["transcript_artifact"]["artifact_id"])
    assert open(transcript["file"], encoding="utf-8").read() == "A verified local transcript."

    summary = SummaryService(ValidSummaryProvider()).generate_summary(transcript["artifact_id"])
    assert summary["success"] is True
    summary_record = artifacts.get_artifact(summary["summary_artifact"]["artifact_id"])
    assert open(summary_record["file"], encoding="utf-8").read() == "Summary: A verified local transcript."


def test_voice_provider_retries_one_transient_failure_before_persisting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = ArtifactManagerService()
    audio = create_test_audio(artifacts)
    transcription_provider = FlakyTranscriptionProvider()

    transcription = TranscriptService(transcription_provider).generate_transcript(audio["artifact_id"])

    assert transcription["success"] is True
    assert transcription_provider.calls == 2

    summary_provider = FlakySummaryProvider()
    summary = SummaryService(summary_provider).generate_summary(
        transcription["transcript_artifact"]["artifact_id"]
    )

    assert summary["success"] is True
    assert summary_provider.calls == 2
