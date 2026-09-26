from datetime import datetime
from typing import Protocol

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService
)


class TranscriptionProvider(Protocol):
    def transcribe(self, audio_path: str) -> str:
        ...


class TranscriptService:

    def __init__(self, provider: TranscriptionProvider | None = None):

        self.artifacts = (
            ArtifactManagerService()
        )
        self.provider = provider

    def generate_transcript(
        self,
        audio_artifact_id: str
    ):

        audio_artifact = (
            self.artifacts.get_artifact(
                audio_artifact_id
            )
        )

        if not audio_artifact:

            return {

                "success":
                False,

                "message":
                "Audio artifact not found"
            }

        if audio_artifact[
            "type"
        ] != "audio":

            return {

                "success":
                False,

                "message":
                "Artifact is not audio"
            }

        if self.provider is None:
            return {
                "success": False,
                "code": "provider_unavailable",
                "message": "Audio is stored, but no speech-to-text provider is configured.",
            }

        transcript_text = self.provider.transcribe(
            audio_artifact["file"]
        )

        if not isinstance(transcript_text, str) or not transcript_text.strip():
            return {
                "success": False,
                "code": "empty_transcript",
                "message": "The transcription provider returned no transcript.",
            }

        transcript_artifact = (

            self.artifacts
            .create_artifact(

                artifact_type=
                "transcripts",

                content=
                transcript_text,

                source=
                audio_artifact_id,

                extension=
                "txt"
            )
        )

        return {

            "success":
            True,

            "audio_artifact":
            audio_artifact_id,

            "transcript_artifact":
            transcript_artifact,

            "created":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }