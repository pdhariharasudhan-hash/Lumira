from datetime import datetime
from typing import Protocol

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService
)


class ImageGenerationProvider(Protocol):
    def generate(self, prompt: str, image_type: str) -> dict:
        ...


class ImageGenerationService:

    def __init__(self, provider: ImageGenerationProvider | None = None):

        self.artifacts = (
            ArtifactManagerService()
        )
        if provider is None:
            from app.services.providers.provider_registry import ProviderRegistry

            provider = ProviderRegistry.get("image_generation")
        self.provider = provider

    def generate(
        self,
        prompt: str,
        image_type: str = "image"
    ):

        supported_types = {

            "image",
            "diagram",
            "blueprint",
            "schematic"
        }

        if image_type not in supported_types:

            return {

                "success":
                False,

                "message":
                f"Unsupported image type: {image_type}"
            }

        if self.provider is None:
            return {
                "success": False,
                "code": "provider_unavailable",
                "message": "No image rendering provider is configured; no image artifact was created.",
            }

        try:
            result = self.provider.generate(prompt, image_type)
        except Exception:
            return {
                "success": False,
                "code": "provider_error",
                "message": "The image provider failed; no image artifact was created.",
            }
        if not isinstance(result, dict) or result.get("success") is not True:
            return {
                "success": False,
                "code": "provider_failed",
                "message": "The image provider did not report a successful render.",
            }

        image_bytes = result.get("content")
        extension = str(result.get("extension", "png")).lower()
        if not isinstance(image_bytes, bytes) or extension not in {"png", "jpg", "jpeg", "webp"}:
            return {
                "success": False,
                "code": "invalid_provider_response",
                "message": "The image provider must return image bytes and a supported image extension.",
            }
        signatures = {
            "png": image_bytes.startswith(b"\x89PNG\r\n\x1a\n"),
            "jpg": image_bytes.startswith(b"\xff\xd8\xff"),
            "jpeg": image_bytes.startswith(b"\xff\xd8\xff"),
            "webp": image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP",
        }
        if not signatures[extension]:
            return {
                "success": False,
                "code": "invalid_provider_response",
                "message": "The image provider output does not match its declared image format.",
            }

        try:
            artifact = self.artifacts.create_binary_artifact(
                "images",
                image_bytes,
                "image_generation",
                extension,
            )
        except ValueError as error:
            return {"success": False, "code": "invalid_provider_output", "message": str(error)}
        except Exception:
            return {
                "success": False,
                "code": "artifact_storage_failed",
                "message": "The image was rendered but could not be stored as an artifact.",
            }

        return {

            "success":
            True,

            "prompt":
            prompt,

            "image_type":
            image_type,

            "artifact": artifact,

            "created":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }
