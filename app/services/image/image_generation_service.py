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

        result = self.provider.generate(prompt, image_type)
        if not isinstance(result, dict) or not result.get("success"):
            return result if isinstance(result, dict) else {
                "success": False,
                "code": "invalid_provider_response",
                "message": "The image provider returned an invalid response.",
            }

        return {

            "success":
            True,

            "prompt":
            prompt,

            "image_type":
            image_type,

            "provider_result":
            result,

            "created":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }