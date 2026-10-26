from __future__ import annotations

from app.services.providers.provider_registry import ProviderRegistry
from app.services.resources.resource_budget_service import ResourceBudgetService


class ImageUnderstandingService:
    """Validates image bytes and delegates analysis to an explicitly configured provider."""

    MAX_IMAGE_BYTES = 10_000_000
    MAX_PROMPT_CHARS = 4_000

    def __init__(self, provider=None) -> None:
        self.provider = provider if provider is not None else ProviderRegistry.get("image_understanding")

    @staticmethod
    def _valid_image(data: bytes) -> bool:
        return (
            data.startswith(b"\x89PNG\r\n\x1a\n")
            or data.startswith(b"\xff\xd8\xff")
            or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
        )

    def analyze(self, image_bytes: bytes, prompt: str = "Describe this image and extract any readable text.") -> dict:
        if not isinstance(image_bytes, bytes) or not image_bytes or len(image_bytes) > self.MAX_IMAGE_BYTES:
            return {"success": False, "code": "invalid_image", "message": "Image is empty or exceeds the 10 MB limit."}
        if not self._valid_image(image_bytes):
            return {"success": False, "code": "invalid_image", "message": "Only PNG, JPEG, and WebP images are supported."}
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > self.MAX_PROMPT_CHARS:
            return {"success": False, "code": "invalid_prompt", "message": "Prompt is empty or exceeds the 4,000-character limit."}
        try:
            guidance = ResourceBudgetService().execution_guidance()
        except Exception:
            guidance = {}
        if guidance.get("defer_optional_heavy_media_work") is True:
            return {
                "success": False,
                "state": "deferred",
                "code": "resource_pressure_deferred",
                "resource_pressure": guidance.get("resource_pressure", "unknown"),
                "message": "Image analysis was deferred because available system memory is constrained.",
            }
        if self.provider is None:
            return {"success": False, "code": "provider_unavailable", "message": "No image-understanding provider is configured; no analysis was produced."}
        try:
            result = self.provider.analyze(image_bytes, prompt.strip())
        except Exception:
            return {"success": False, "code": "provider_error", "message": "The image-understanding provider failed; no analysis was produced."}
        if not isinstance(result, dict) or result.get("success") is not True:
            return {"success": False, "code": "provider_failed", "message": "The provider did not report a successful analysis."}
        description = result.get("description")
        if not isinstance(description, str) or not description.strip() or len(description) > 20_000:
            return {"success": False, "code": "invalid_provider_response", "message": "The provider returned an invalid analysis."}
        return {"success": True, "description": description.strip(), "model": str(result.get("model", "configured provider"))[:100]}
