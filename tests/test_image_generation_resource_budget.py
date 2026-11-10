from __future__ import annotations

from app.services.image.image_generation_service import ImageGenerationService
from app.services.resources.resource_budget_service import ResourceBudgetService


class NeverCalledImageProvider:
    provider_scope = "local"
    def generate(self, prompt: str, image_type: str) -> dict:
        raise AssertionError("provider must not be called for invalid or deferred requests")


def test_image_generation_defers_when_memory_pressure_requires_it(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "constrained",
            "defer_optional_heavy_media_work": True,
        },
    )

    service = ImageGenerationService(provider=NeverCalledImageProvider())
    result = service.generate("Create a simple circuit diagram", "diagram")

    assert result["success"] is False
    assert result["state"] == "deferred"
    assert result["code"] == "resource_pressure_deferred"
    assert result["resource_pressure"] == "constrained"


def test_image_generation_rejects_empty_or_oversized_prompts(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "normal",
            "defer_optional_heavy_media_work": False,
        },
    )

    service = ImageGenerationService(provider=NeverCalledImageProvider())

    empty_result = service.generate("   ")
    oversized_result = service.generate("x" * (service.MAX_PROMPT_CHARS + 1))

    assert empty_result["success"] is False
    assert empty_result["code"] == "invalid_prompt"
    assert oversized_result["success"] is False
    assert oversized_result["code"] == "invalid_prompt"

from app.services.image.image_understanding_service import ImageUnderstandingService


class NeverCalledVisionProvider:
    provider_scope = "local"
    def analyze(self, image_bytes: bytes, prompt: str) -> dict:
        raise AssertionError("provider must not be called while media work is deferred")


def test_image_understanding_defers_when_memory_pressure_requires_it(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "critical",
            "defer_optional_heavy_media_work": True,
        },
    )

    service = ImageUnderstandingService(provider=NeverCalledVisionProvider())
    # Valid PNG signature is sufficient to reach the resource guard.
    result = service.analyze(b"\x89PNG\r\n\x1a\n")

    assert result["success"] is False
    assert result["state"] == "deferred"
    assert result["code"] == "resource_pressure_deferred"
    assert result["resource_pressure"] == "critical"

class OversizedImageProvider:
    provider_scope = "local"
    def generate(self, prompt: str, image_type: str) -> dict:
        return {
            "success": True,
            "content": b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 10,
            "extension": "png",
        }


def test_image_generation_rejects_oversized_provider_output(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {
            "resource_pressure": "normal",
            "defer_optional_heavy_media_work": False,
        },
    )

    service = ImageGenerationService(provider=OversizedImageProvider())
    monkeypatch.setattr(service, "MAX_IMAGE_BYTES", 8)

    result = service.generate("Create a small image")

    assert result["success"] is False
    assert result["code"] == "image_size_limit_exceeded"
    assert result["max_image_bytes"] == 8

class InvalidImageResponseProvider:
    provider_scope = "local"
    def generate(self, prompt: str, image_type: str) -> dict:
        raise ValueError("Image service returned an invalid image response.")


def test_image_generation_preserves_safe_provider_error_detail(monkeypatch):
    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {"resource_pressure": "normal", "defer_optional_heavy_media_work": False},
    )
    result = ImageGenerationService(provider=InvalidImageResponseProvider()).generate("A small rocket")
    assert result["success"] is False
    assert result["code"] == "invalid_provider_response"
    assert result["message"] == "Image service returned an invalid image response."
