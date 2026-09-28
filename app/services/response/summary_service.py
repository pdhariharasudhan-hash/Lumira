from datetime import datetime
from typing import Protocol

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService
)


class SummaryProvider(Protocol):
    def summarize(self, transcript: str) -> str:
        ...


class SummaryService:

    def __init__(self, provider: SummaryProvider | None = None):

        self.artifacts = (
            ArtifactManagerService()
        )
        if provider is None:
            from app.services.providers.provider_registry import ProviderRegistry

            provider = ProviderRegistry.get("summarization")
        self.provider = provider

    def generate_summary(
        self,
        transcript_artifact_id: str
    ):

        transcript_artifact = (
            self.artifacts.get_artifact(
                transcript_artifact_id
            )
        )

        if not transcript_artifact:

            return {

                "success":
                False,

                "message":
                "Transcript artifact not found"
            }

        if transcript_artifact[
            "type"
        ] != "transcripts":

            return {

                "success":
                False,

                "message":
                "Artifact is not a transcript"
            }

        if self.provider is None:
            return {
                "success": False,
                "code": "provider_unavailable",
                "message": "No transcript summarization provider is configured.",
            }

        try:
            transcript_path = self.artifacts.get_artifact_path(transcript_artifact_id)
            if transcript_path is None or not transcript_path.is_file() or transcript_path.stat().st_size > self.artifacts.MAX_CONTENT_LENGTH:
                return {"success": False, "code": "invalid_transcript_artifact", "message": "Transcript artifact is unavailable or exceeds the processing limit."}
            transcript_text = transcript_path.read_text(encoding="utf-8")
        except Exception:

            return {

                "success":
                False,

                "code": "artifact_read_failed",
                "message": "Transcript artifact could not be read safely.",
            }

        try:
            summary_text = self.provider.summarize(transcript_text)
        except Exception:
            return {
                "success": False,
                "code": "provider_error",
                "message": "The summarization provider failed; no summary was created.",
            }
        if not isinstance(summary_text, str) or not summary_text.strip():
            return {
                "success": False,
                "code": "empty_summary",
                "message": "The summary provider returned no summary.",
            }
        if len(summary_text) > self.artifacts.MAX_CONTENT_LENGTH:
            return {"success": False, "code": "provider_output_too_large", "message": "The summarization provider output exceeds the artifact limit."}

        try:
            summary_artifact = self.artifacts.create_artifact(

                artifact_type=
                "summaries",

                content=
                summary_text,

                source=
                transcript_artifact_id,

                extension=
                "txt"
            )
        except Exception:
            return {
                "success": False,
                "code": "artifact_storage_failed",
                "message": "The summary was produced but could not be stored as an artifact.",
            }

        return {

            "success":
            True,

            "transcript_artifact":
            transcript_artifact_id,

            "summary_artifact":
            summary_artifact,

            "created":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }
