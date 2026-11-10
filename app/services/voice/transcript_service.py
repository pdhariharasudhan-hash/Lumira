from datetime import datetime
from typing import Protocol

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService
)



from app.services.providers.provider_access_policy_service import ProviderAccessDenied, ProviderAccessPolicyService

class TranscriptionProvider(Protocol):
    def transcribe(self, audio_path: str) -> str:
        ...


class TranscriptService:
    MAX_PROVIDER_ATTEMPTS = 2

    def __init__(self, provider: TranscriptionProvider | None = None, *, provider_policy=None):

        self.artifacts = (
            ArtifactManagerService()
        )
        if provider is None:
            from app.services.providers.provider_registry import ProviderRegistry

            provider = ProviderRegistry.get("transcription")
        self.provider = provider
        self.provider_policy = provider_policy or ProviderAccessPolicyService()

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
            # Only the file header is needed for format validation. Reading the
            # entire recording here needlessly duplicates up to the full upload size
            # in memory before handing the path to the transcription provider.
            with audio_path.open("rb") as audio_file:
                signature = audio_file.read(12)
            if extension not in self.artifacts.BINARY_FORMATS["audio"] or not self.artifacts._has_binary_signature(
                "audio", signature, extension
            ):
                return {"success": False, "code": "invalid_audio_artifact", "message": "Audio content does not match a supported audio format."}
        except Exception:
            return {
                "success": False,
                "code": "invalid_audio_artifact",
                "message": "Audio artifact could not be read safely.",
            }

        # Reuse an existing transcript for this audio artifact before invoking
        # a provider. This keeps retries after summary/memory failures from
        # creating duplicate transcript artifacts.
        list_artifacts = getattr(self.artifacts, "get_all_artifacts", None)
        verify_content = getattr(self.artifacts, "verify_artifact_content", None)
        if callable(list_artifacts) and callable(verify_content):
            try:
                existing = next(
                    (
                        item for item in list_artifacts()
                        if item.get("type") == "transcripts"
                        and item.get("source") == audio_artifact_id
                        and not item.get("archived", False)
                    ),
                    None,
                )
                if existing is not None:
                    integrity = verify_content(existing.get("artifact_id", ""))
                    if not integrity.get("success"):
                        return {
                            "success": False,
                            "code": integrity.get("code", "artifact_integrity_failed"),
                            "message": "An existing transcript failed integrity verification; it was not replaced.",
                        }
                    existing_path = self.artifacts.get_artifact_path(existing["artifact_id"])
                    if existing_path is None or not existing_path.is_file():
                        return {
                            "success": False,
                            "code": "artifact_content_missing",
                            "message": "An existing transcript artifact is unavailable; it was not replaced.",
                        }
                    existing_text = existing_path.read_text(encoding="utf-8")
                    if (
                        not existing_text.strip()
                        or len(existing_text) > self.artifacts.MAX_CONTENT_LENGTH
                    ):
                        return {
                            "success": False,
                            "code": "artifact_content_invalid",
                            "message": "An existing transcript contains invalid content; it was not replaced.",
                        }
                    from app.services.language.language_detection_service import LanguageDetectionService

                    language = LanguageDetectionService().detect(existing_text)
                    return {
                        "success": True,
                        "audio_artifact": audio_artifact_id,
                        "transcript_text": existing_text,
                        "transcript_artifact": existing,
                        "language": language["language"],
                        "language_confidence": language["confidence"],
                        "created": existing.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        "reused": True,
                    }
            except Exception:
                return {
                    "success": False,
                    "code": "artifact_lookup_failed",
                    "message": "Existing transcripts could not be checked safely; duplicate generation was prevented.",
                }

        if self.provider is None:
            return {
                "success": False,
                "code": "provider_unavailable",
                "message": "Audio is stored, but no speech-to-text provider is configured.",
            }

        supported_extensions = getattr(self.provider, "SUPPORTED_EXTENSIONS", None)
        if isinstance(supported_extensions, (set, frozenset, list, tuple)) and extension not in supported_extensions:
            return {
                "success": False,
                "code": "unsupported_audio_format",
                "message": "The configured transcription provider does not support this audio format.",
                "format": extension,
                "supported_formats": sorted(
                    value for value in supported_extensions
                    if isinstance(value, str)
                ),
            }

        try:
            self.provider_policy.authorize(self.provider, "audio transcription")
            transcript_text = None
            for attempt in range(self.MAX_PROVIDER_ATTEMPTS):
                try:
                    transcript_text = self.provider.transcribe(str(audio_path))
                    break
                except RuntimeError as error:
                    if "deferred" in str(error).lower():
                        raise
                    if attempt + 1 == self.MAX_PROVIDER_ATTEMPTS:
                        raise
        except ProviderAccessDenied as error:
            return {"success": False, "code": error.code, "message": error.user_message}
        except RuntimeError as error:
            if "deferred" in str(error).lower():
                return {
                    "success": False,
                    "state": "deferred",
                    "code": "resource_pressure_deferred",
                    "message": "Transcription was deferred because available system memory is constrained. The audio artifact is preserved.",
                }
            return {
                "success": False,
                "code": "provider_error",
                "message": "The transcription provider failed; no transcript was created.",
            }
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

            "transcript_text": transcript_text,

            "transcript_artifact":
            transcript_artifact,

            "language": language["language"],

            "language_confidence": language["confidence"],

            "created":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }
