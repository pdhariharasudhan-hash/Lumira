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

        transcript_file = (
            transcript_artifact[
                "file"
            ]
        )

        try:

            with open(
                transcript_file,
                "r",
                encoding="utf-8"
            ) as f:

                transcript_text = (
                    f.read()
                )

        except Exception as e:

            return {

                "success":
                False,

                "message":
                str(e)
            }

        summary_text = self.provider.summarize(transcript_text)
        if not isinstance(summary_text, str) or not summary_text.strip():
            return {
                "success": False,
                "code": "empty_summary",
                "message": "The summary provider returned no summary.",
            }

        summary_artifact = (

            self.artifacts
            .create_artifact(

                artifact_type=
                "summaries",

                content=
                summary_text,

                source=
                transcript_artifact_id,

                extension=
                "txt"
            )
        )

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