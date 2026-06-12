from datetime import datetime

from app.services.artifact_manager_service import (
    ArtifactManagerService
)


class TranscriptService:

    def __init__(self):

        self.artifacts = (
            ArtifactManagerService()
        )

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

        transcript_text = (

            "[MOCK TRANSCRIPT]\n\n"

            f"Audio File: "
            f"{audio_artifact['file']}\n\n"

            "Transcript generation "
            "placeholder.\n"

            "Future version will use "
            "Whisper for Tamil, English "
            "and mixed-language support."
        )

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