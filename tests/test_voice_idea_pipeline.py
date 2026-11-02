from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService


class FakeTranscript:
    def generate_transcript(self, audio_id):
        return {
            "success": True,
            "audio_artifact": audio_id,
            "transcript_artifact": {"artifact_id": "transcript-1"},
            "language": "ta-en",
        }


class FakeSummary:
    def generate_summary(self, transcript_id):
        assert transcript_id == "transcript-1"
        return {
            "success": True,
            "summary_text": "A new robot idea",
            "summary_artifact": {"artifact_id": "summary-1"},
        }


class FakeMemory:
    def record_experience(self, *args, **kwargs):
        assert kwargs["artifact_ids"] == ["audio-1", "transcript-1", "summary-1"]
        return {"experience_id": "experience-1"}


def test_voice_idea_pipeline_connects_existing_services():
    pipeline = VoiceIdeaPipelineService(FakeTranscript(), FakeSummary(), FakeMemory())
    result = pipeline.process("audio-1", project_id="project-1")
    assert result["success"] is True
    assert result["stage"] == "complete"
    assert result["memory_reference"] == "experience-1"


def test_voice_idea_pipeline_rejects_missing_audio_id():
    pipeline = VoiceIdeaPipelineService(FakeTranscript(), FakeSummary(), FakeMemory())
    result = pipeline.process("")
    assert result["success"] is False
    assert result["stage"] == "validate"
