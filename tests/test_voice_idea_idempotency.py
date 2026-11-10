from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService


class TranscriptMustNotRun:
    def generate_transcript(self, audio_id):
        raise AssertionError("a previously completed voice capture must not be transcribed again")


class MemoryWithExistingExperience:
    def get_all(self):
        return {
            "experiences": [
                {
                    "experience_id": "experience-1",
                    "artifact_ids": ["audio-1", "transcript-1", "summary-1"],
                }
            ]
        }

    def record_experience(self, *args, **kwargs):
        raise AssertionError("a duplicate memory experience must not be written")


def test_reprocessing_completed_voice_capture_is_idempotent():
    service = VoiceIdeaPipelineService(
        transcript_service=TranscriptMustNotRun(),
        memory_service=MemoryWithExistingExperience(),
    )

    result = service.process("audio-1")

    assert result["success"] is True
    assert result["stage"] == "complete"
    assert result["memory_reference"] == "experience-1"
    assert result["memory_status"]["state"] == "already_saved"
    assert result["preserved_artifacts"] == ["audio-1", "transcript-1", "summary-1"]


def test_different_audio_capture_does_not_reuse_existing_experience():
    class Transcript:
        def generate_transcript(self, audio_id):
            assert audio_id == "audio-2"
            return {"success": False, "code": "provider_unavailable"}

    service = VoiceIdeaPipelineService(
        transcript_service=Transcript(),
        memory_service=MemoryWithExistingExperience(),
    )

    result = service.process("audio-2")

    assert result["success"] is False
    assert result["stage"] == "transcript"
    assert result["transcript"]["code"] == "provider_unavailable"



def test_memory_lookup_failure_stops_before_retranscription():
    class MemoryUnavailable:
        def get_all(self):
            raise OSError("memory store unavailable")

    service = VoiceIdeaPipelineService(
        transcript_service=TranscriptMustNotRun(),
        memory_service=MemoryUnavailable(),
    )

    result = service.process("audio-1")

    assert result["success"] is False
    assert result["stage"] == "memory_preflight"
    assert result["code"] == "memory_lookup_failed"
    assert result["recoverable"] is True
    assert result["preserved_artifacts"] == ["audio-1"]
