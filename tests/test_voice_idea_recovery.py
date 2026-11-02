from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService


class Transcript:
    def generate_transcript(self, audio_id):
        return {"success": True, "transcript_artifact": {"artifact_id": "t1"}, "transcript_text": "idea"}


class SummaryFailure:
    def generate_summary(self, transcript_id):
        return {"success": False, "code": "provider_unavailable"}


class Memory:
    def record_experience(self, *args, **kwargs):
        raise AssertionError("memory must not be written before summary succeeds")


class Language:
    def detect(self, text):
        return {"language": "en"}


def test_summary_failure_preserves_voice_idea_for_retry():
    result = VoiceIdeaPipelineService(Transcript(), SummaryFailure(), Memory(), Language()).process("a1")
    assert result["success"] is False
    assert result["recoverable"] is True
    assert result["preserved_artifacts"] == ["a1", "t1"]
