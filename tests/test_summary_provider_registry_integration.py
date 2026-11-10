from pathlib import Path
import pytest

from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.providers.provider_registry import ProviderRegistry
from app.services.response.summary_service import SummaryService
from app.services.resources.resource_budget_service import ResourceBudgetService


@pytest.fixture(autouse=True)
def normal_resource_budget(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {"defer_optional_heavy_media_work": False, "resource_pressure": "normal"},
    )


class RegisteredSummaryProvider:
    provider_scope = "local"

    def __init__(self):
        self.received_transcript = None
        self.calls = 0

    def summarize(self, transcript: str) -> str:
        self.calls += 1
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

        replay = SummaryService().generate_summary(transcript["artifact_id"])
        assert replay["success"] is True
        assert replay["reused"] is True
        assert replay["summary_artifact"]["artifact_id"] == result["summary_artifact"]["artifact_id"]
        assert provider.calls == 1
    finally:
        ProviderRegistry.clear()


def test_summary_retry_fails_closed_when_existing_summary_is_corrupt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ProviderRegistry.clear()
    provider = RegisteredSummaryProvider()
    ProviderRegistry.register("summarization", provider)
    try:
        artifacts = ArtifactManagerService()
        transcript = artifacts.create_artifact("transcripts", "A transcript.", "test", "txt")
        first = SummaryService().generate_summary(transcript["artifact_id"])
        summary_id = first["summary_artifact"]["artifact_id"]
        Path(first["summary_artifact"]["file"]).write_text("tampered", encoding="utf-8")

        replay = SummaryService().generate_summary(transcript["artifact_id"])

        assert replay["success"] is False
        assert replay["code"] == "artifact_content_corrupt"
        assert provider.calls == 1
        assert artifacts.get_artifact(summary_id) is not None
    finally:
        ProviderRegistry.clear()
