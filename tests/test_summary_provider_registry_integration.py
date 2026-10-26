from pathlib import Path

from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.providers.provider_registry import ProviderRegistry
from app.services.response.summary_service import SummaryService


class RegisteredSummaryProvider:
    def __init__(self):
        self.received_transcript = None

    def summarize(self, transcript: str) -> str:
        self.received_transcript = transcript
        return f"Verified summary: {transcript}"


def test_summary_service_uses_registered_provider_and_persists_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ProviderRegistry.clear()
    provider = RegisteredSummaryProvider()
    ProviderRegistry.register("summarization", provider)
    try:
        artifacts = ArtifactManagerService()
        transcript = artifacts.create_artifact(
            "transcripts", "Lumira registry integration transcript.", "test", "txt"
        )

        result = SummaryService().generate_summary(transcript["artifact_id"])

        assert result["success"] is True
        assert result["summary_text"] == "Verified summary: Lumira registry integration transcript."
        assert provider.received_transcript == "Lumira registry integration transcript."
        summary_record = artifacts.get_artifact(result["summary_artifact"]["artifact_id"])
        assert summary_record["type"] == "summaries"
        assert summary_record["source"] == transcript["artifact_id"]
        assert Path(summary_record["file"]).read_text(encoding="utf-8") == (
            "Verified summary: Lumira registry integration transcript."
        )
    finally:
        ProviderRegistry.clear()
