from typing import Protocol

from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.providers.provider_registry import ProviderRegistry



from app.services.providers.provider_access_policy_service import ProviderAccessDenied, ProviderAccessPolicyService

class WakeWordProvider(Protocol):
    def detect(self, audio_path: str) -> dict:
        """Return whether the configured local recognizer heard Lumira."""


class SpeechPlaybackProvider(Protocol):
    def synthesize(self, text: str, language: str) -> dict:
        """Return synthesized audio bytes or a structured provider failure."""


class WakeWordActivationService:
    def __init__(self, provider: WakeWordProvider | None = None, *, provider_policy=None):
        self.provider = ProviderRegistry.get("wake_word") if provider is None else provider
        self.provider_policy = provider_policy or ProviderAccessPolicyService()
        self.artifacts = ArtifactManagerService()

    def activate(self, audio_artifact_id: str) -> dict:
        artifact = self.artifacts.get_artifact(audio_artifact_id)
        if not artifact or artifact.get("type") != "audio":
            return {"success": False, "code": "audio_artifact_not_found", "message": "A stored audio artifact is required."}
        if self.provider is None:
            return {"success": False, "code": "provider_unavailable", "message": "No local Lumira wake-word detector is configured."}
        try:
            path = self.artifacts.get_artifact_path(audio_artifact_id)
            if path is None or not path.is_file() or path.stat().st_size > self.artifacts.MAX_BINARY_CONTENT_BYTES:
                return {"success": False, "code": "invalid_audio_artifact", "message": "Audio artifact is unavailable or exceeds the processing limit."}
            self.provider_policy.authorize(self.provider, "wake-word detection")
            result = self.provider.detect(str(path))
        except ProviderAccessDenied as error:
            return {"success": False, "code": error.code, "message": error.user_message}
        except Exception:
            return {"success": False, "code": "provider_error", "message": "The wake-word detector failed; Lumira was not activated."}
        if not isinstance(result, dict) or result.get("success") is not True or not isinstance(result.get("detected"), bool):
            return {"success": False, "code": "invalid_provider_response", "message": "The wake-word detector returned an invalid result."}
        return {
            "success": True,
            "activated": result["detected"],
            "wake_word": "Lumira" if result["detected"] else None,
            "audio_artifact_id": audio_artifact_id,
        }


class SpeechPlaybackService:
    SUPPORTED_LANGUAGES = {"en", "ta", "ta-en"}

    def __init__(self, provider: SpeechPlaybackProvider | None = None, *, provider_policy=None):
        self.provider = ProviderRegistry.get("speech_synthesis") if provider is None else provider
        self.provider_policy = provider_policy or ProviderAccessPolicyService()
        self.artifacts = ArtifactManagerService()

    def play(self, text: str, language: str = "en") -> dict:
        if not isinstance(text, str) or not text.strip() or len(text) > self.artifacts.MAX_CONTENT_LENGTH:
            return {"success": False, "code": "invalid_request", "message": "Playback text must contain 1 to 1000000 characters."}
        if language not in self.SUPPORTED_LANGUAGES:
            return {"success": False, "code": "unsupported_language", "message": "Playback language must be en, ta, or ta-en."}
        if self.provider is None:
            return {"success": False, "code": "provider_unavailable", "message": "No speech synthesis provider is configured."}
        try:
            self.provider_policy.authorize(self.provider, "speech synthesis")
            result = self.provider.synthesize(text.strip(), language)
        except ProviderAccessDenied as error:
            return {"success": False, "code": error.code, "message": error.user_message}
        except RuntimeError as error:
            if "deferred" in str(error).lower():
                return {
                    "success": False,
                    "state": "deferred",
                    "code": "resource_pressure_deferred",
                    "message": "Speech synthesis was deferred because available system memory is constrained.",
                }
            return {"success": False, "code": "provider_error", "message": "The speech synthesis provider failed; no audio was created."}
        except Exception:
            return {"success": False, "code": "provider_error", "message": "The speech synthesis provider failed; no audio was created."}
        if not isinstance(result, dict) or result.get("success") is not True:
            return {"success": False, "code": "provider_failed", "message": "The speech synthesis provider did not report success."}
        content = result.get("content")
        extension = str(result.get("extension", "")).lower()
        try:
            artifact = self.artifacts.create_binary_artifact("audio", content, "speech_playback", extension)
        except (ValueError, TypeError):
            return {"success": False, "code": "invalid_provider_response", "message": "The speech provider must return supported audio bytes with a matching format."}
        except Exception:
            return {"success": False, "code": "artifact_storage_failed", "message": "Synthesized audio could not be stored."}
        return {"success": True, "language": language, "artifact": artifact}
