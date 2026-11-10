from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService


class FakeTranscript:
    def generate_transcript(self, audio_id):
        return {
            "success": True,
            "audio_artifact": audio_id,
            "transcript_artifact": {"artifact_id": "transcript-1"},
            "transcript_text": "Build a robot idea",
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
    def __init__(self, fail=False):
        self.fail = fail
        self.call = None

    def record_experience(self, *args, **kwargs):
        self.call = (args, kwargs)
        assert args[0] == "workflow"
        assert kwargs["verified"] is False
        assert kwargs["artifact_ids"] == [
            "audio-1",
            "transcript-1",
            "summary-1",
        ]
        if self.fail:
            raise RuntimeError("simulated memory write failure")
        return {"experience_id": "experience-1"}


class FakeLanguage:
    def detect(self, text):
        assert "robot" in text
        return {"language": "en", "confidence": 1.0}


class FailedTranscript:
    def generate_transcript(self, audio_id):
        return {"success": False, "code": "transcription_provider_unavailable"}


class ForbiddenSummary:
    def generate_summary(self, transcript_id):
        raise AssertionError("summary must not run after transcription failure")


class ForbiddenMemory:
    def record_experience(self, *args, **kwargs):
        raise AssertionError("memory must not run after transcription failure")


def _patch_core_context(monkeypatch):
    from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService

    monkeypatch.setattr(
        CoreRuntimeBridgeService,
        "execution_context",
        lambda self, *args, **kwargs: {"success": True},
    )


def test_voice_idea_pipeline_connects_existing_services(monkeypatch):
    _patch_core_context(monkeypatch)
    memory = FakeMemory()
    pipeline = VoiceIdeaPipelineService(
        FakeTranscript(),
        FakeSummary(),
        memory,
        FakeLanguage(),
    )

    result = pipeline.process("audio-1", project_id="project-1")

    assert result["success"] is True
    assert result["stage"] == "complete"
    assert result["memory_reference"] == "experience-1"
    assert result["memory_status"] == {"success": True, "state": "saved"}
    assert memory.call[0] == ("workflow",)


def test_voice_idea_pipeline_preserves_artifacts_when_memory_write_fails(monkeypatch):
    _patch_core_context(monkeypatch)
    pipeline = VoiceIdeaPipelineService(
        FakeTranscript(),
        FakeSummary(),
        FakeMemory(fail=True),
        FakeLanguage(),
    )

    result = pipeline.process("audio-1")

    assert result["success"] is False
    assert result["stage"] == "memory"
    assert result["recoverable"] is True
    assert result["preserved_artifacts"] == [
        "audio-1",
        "transcript-1",
        "summary-1",
    ]
    assert result["memory_status"]["code"] == "memory_persistence_failed"


def test_voice_idea_pipeline_stops_before_summary_and_memory_on_transcription_failure():
    pipeline = VoiceIdeaPipelineService(
        FailedTranscript(),
        ForbiddenSummary(),
        ForbiddenMemory(),
        FakeLanguage(),
    )

    result = pipeline.process("audio-1")

    assert result == {
        "success": False,
        "stage": "transcript",
        "audio_artifact": "audio-1",
        "transcript": {"success": False, "code": "transcription_provider_unavailable"},
    }
