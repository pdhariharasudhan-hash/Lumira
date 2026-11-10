from types import SimpleNamespace

from app.services.response.summary_service import SummaryService
from app.services.resources.resource_budget_service import ResourceBudgetService


class NeverCalledSummaryProvider:
    provider_scope = "local"
    def summarize(self, transcript: str) -> str:
        raise AssertionError("summary provider must not be called while deferred")


def test_summary_generation_defers_under_memory_pressure(tmp_path, monkeypatch):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("A short transcript.", encoding="utf-8")

    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "constrained",
            "defer_optional_heavy_media_work": True,
        },
    )

    service = SummaryService(provider=NeverCalledSummaryProvider())
    service.artifacts = SimpleNamespace(
        get_artifact=lambda artifact_id: {
            "artifact_id": artifact_id,
            "type": "transcripts",
        },
        get_artifact_path=lambda artifact_id: transcript_path,
        MAX_CONTENT_LENGTH=1_000_000,
    )

    result = service.generate_summary("transcript-1")

    assert result["success"] is False
    assert result["state"] == "deferred"
    assert result["code"] == "resource_pressure_deferred"
    assert result["resource_pressure"] == "constrained"
