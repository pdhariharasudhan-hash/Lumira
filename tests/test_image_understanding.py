import base64

from fastapi import HTTPException

from app.routes import image_understanding as route
from app.services.image.image_understanding_service import ImageUnderstandingService


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"minimal-test-image"


class FakeVisionProvider:
    def analyze(self, image_bytes, prompt):
        assert image_bytes == PNG_HEADER
        assert prompt == "Read this image"
        return {"success": True, "description": "A test image with readable text.", "model": "test-model"}


def test_image_understanding_requires_a_provider():
    result = ImageUnderstandingService(provider=None).analyze(PNG_HEADER)
    assert result["success"] is False
    assert result["code"] == "provider_unavailable"


def test_image_understanding_validates_image_and_prompt():
    service = ImageUnderstandingService(provider=FakeVisionProvider())
    assert service.analyze(b"not-an-image")["code"] == "invalid_image"
    assert service.analyze(PNG_HEADER, " ")["code"] == "invalid_prompt"


def test_image_understanding_returns_validated_provider_description():
    result = ImageUnderstandingService(provider=FakeVisionProvider()).analyze(PNG_HEADER, "Read this image")
    assert result == {
        "success": True,
        "description": "A test image with readable text.",
        "model": "test-model",
    }


def test_image_analysis_route_returns_description(monkeypatch):
    class FakeService:
        def analyze(self, image_bytes, prompt):
            assert image_bytes == PNG_HEADER
            assert prompt == "Read this image"
            return {"success": True, "description": "A test image with readable text."}

    monkeypatch.setattr(route, "ImageUnderstandingService", FakeService)
    result = route.analyze_image(route.ImageAnalysisRequest(
        image_base64=base64.b64encode(PNG_HEADER).decode("ascii"),
        prompt="Read this image",
    ))
    assert result["success"] is True
    assert result["description"] == "A test image with readable text."


def test_image_analysis_route_rejects_invalid_base64():
    try:
        route.analyze_image(route.ImageAnalysisRequest(image_base64="!" * 20))
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("invalid base64 must be rejected")


def test_vision_provider_parses_openai_compatible_response(monkeypatch):
    import json
    from app.services.providers import openai_compatible_vision_provider as provider_module
    from app.services.providers.openai_compatible_vision_provider import OpenAICompatibleVisionProvider

    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            yield json.dumps({"choices": [{"message": {"content": "  A labeled circuit board.  "}}]}).encode()

        def close(self):
            return None

    monkeypatch.setattr(provider_module.requests, "post", lambda *args, **kwargs: FakeResponse())
    provider = OpenAICompatibleVisionProvider(api_key="test-only", base_url="https://example.com/v1", model="test-vision")
    result = provider.analyze(PNG_HEADER, "Read this image")
    assert result["success"] is True
    assert result["description"] == "A labeled circuit board."
    assert result["model"] == "test-vision"


def test_vision_provider_rejects_invalid_image_bytes():
    from app.services.providers.openai_compatible_vision_provider import OpenAICompatibleVisionProvider

    provider = OpenAICompatibleVisionProvider(api_key="test-only", base_url="https://example.com/v1")
    try:
        provider.analyze(b"not-an-image")
    except ValueError as exc:
        assert "PNG, JPEG, or WebP" in str(exc)
    else:
        raise AssertionError("invalid image signature must be rejected")


def test_image_analysis_route_returns_service_unavailable_without_provider(monkeypatch):
    class UnavailableService:
        def analyze(self, image_bytes, prompt):
            return {"success": False, "code": "provider_unavailable", "message": "No image-understanding provider is configured."}

    monkeypatch.setattr(route, "ImageUnderstandingService", UnavailableService)
    request = route.ImageAnalysisRequest(image_base64=base64.b64encode(PNG_HEADER).decode("ascii"))
    try:
        route.analyze_image(request)
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "provider is configured" in exc.detail
    else:
        raise AssertionError("missing provider must return HTTP 503")
