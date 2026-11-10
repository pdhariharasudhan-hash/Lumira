from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService


class Summary:
    def generate_summary(self, transcript_id):
        assert transcript_id == "transcript-1"
        return {
            "success": True,
            "summary_text": "Recovered voice idea summary",
            "summary_artifact": {"artifact_id": "summary-2"},
        }


class Memory:
    def __init__(self, fail=False):
        self.fail = fail
        self.attached = None

    def get_all(self):
        return {
            "experiences": [{
                "experience_id": "experience-1",
                "artifact_ids": ["audio-1", "transcript-1"],
            }]
        }

    def attach_artifacts_to_experience(self, source_id, artifact_ids):
        if self.fail:
            raise OSError("cognitive memory unavailable")
        self.attached = (source_id, artifact_ids)
        return {
            "experience_id": "experience-1",
            "artifact_ids": ["audio-1", "transcript-1", *artifact_ids],
        }


def test_summary_retry_links_recovered_summary_to_existing_voice_memory():
    memory = Memory()
    pipeline = VoiceIdeaPipelineService(summary_service=Summary(), memory_service=memory)

    result = pipeline.retry_summary("transcript-1")

    assert result["success"] is True
    assert result["memory_reference"] == "experience-1"
    assert result["memory_status"] == {"success": True, "state": "updated"}
    assert result["preserved_artifacts"] == ["audio-1", "transcript-1", "summary-2"]
    assert memory.attached == ("transcript-1", ["summary-2"])


def test_summary_retry_reports_link_failure_without_losing_saved_artifacts():
    pipeline = VoiceIdeaPipelineService(summary_service=Summary(), memory_service=Memory(fail=True))

    result = pipeline.retry_summary("transcript-1")

    assert result["success"] is False
    assert result["stage"] == "memory"
    assert result["code"] == "memory_artifact_link_failed"
    assert result["recoverable"] is True
    assert result["preserved_artifacts"] == ["transcript-1", "summary-2"]
