from datetime import datetime

from app.services.artifact_manager_service import (
    ArtifactManagerService
)


class SummaryService:

    def __init__(self):

        self.artifacts = (
            ArtifactManagerService()
        )

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

        summary_text = (

            "[MOCK SUMMARY]\n\n"

            "Transcript successfully "
            "processed.\n\n"

            f"Characters: "
            f"{len(transcript_text)}\n\n"

            "Future versions will use "
            "AI summarization to extract:\n"

            "- key ideas\n"
            "- action items\n"
            "- tags\n"
            "- project concepts\n"
            "- startup ideas\n"
            "- research notes\n"
        )

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