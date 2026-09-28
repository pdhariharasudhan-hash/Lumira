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
        if provider is None:
            from app.services.providers.provider_registry import ProviderRegistry

            provider = ProviderRegistry.get("transcription")
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

        try:
            audio_path = self.artifacts.get_artifact_path(audio_artifact_id)
            if audio_path is None or not audio_path.is_file() or audio_path.stat().st_size > self.artifacts.MAX_BINARY_CONTENT_BYTES:
                return {"success": False, "code": "invalid_audio_artifact", "message": "Audio artifact is unavailable or exceeds the processing limit."}
            extension = audio_path.suffix.lstrip(".").lower()
            if extension not in self.artifacts.BINARY_FORMATS["audio"] or not self.artifacts._has_binary_signature(
                "audio", audio_path.read_bytes(), extension
            ):
                return {"success": False, "code": "invalid_audio_artifact", "message": "Audio content does not match a supported audio format."}
        except Exception:
            return {
                "success": False,
                "code": "invalid_audio_artifact",
                "message": "Audio artifact could not be read safely.",
            }

        if self.provider is None:
            return {
                "success": False,
                "code": "provider_unavailable",
                "message": "Audio is stored, but no speech-to-text provider is configured.",
            }

        try:
            transcript_text = self.provider.transcribe(str(audio_path))
        except Exception:
            return {
                "success": False,
                "code": "provider_error",
                "message": "The transcription provider failed; no transcript was created.",
            }

        if not isinstance(transcript_text, str) or not transcript_text.strip():
            return {
                "success": False,
                "code": "empty_transcript",
                "message": "The transcription provider returned no transcript.",
            }
        if len(transcript_text) > self.artifacts.MAX_CONTENT_LENGTH:
            return {"success": False, "code": "provider_output_too_large", "message": "The transcription provider output exceeds the artifact limit."}

        try:
            transcript_artifact = self.artifacts.create_artifact(

                artifact_type=
                "transcripts",

                content=
                transcript_text,

                source=
                audio_artifact_id,

                extension=
                "txt"
            )
        except Exception:
            return {
                "success": False,
                "code": "artifact_storage_failed",
                "message": "The transcript was produced but could not be stored as an artifact.",
            }

        from app.services.language.language_detection_service import LanguageDetectionService

        language = LanguageDetectionService().detect(transcript_text)
        return {

            "success":
            True,

            "audio_artifact":
            audio_artifact_id,

            "transcript_artifact":
            transcript_artifact,

            "language": language["language"],

            "language_confidence": language["confidence"],

            "created":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }
