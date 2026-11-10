import base64

from fastapi import HTTPException

from app.routes import image_understanding as route
from app.services.image.image_understanding_service import ImageUnderstandingService


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"minimal-test-image"


class FakeVisionProvider:
    provider_scope = "local"
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


def test_image_understanding_returns_validated_provider_description(monkeypatch):
    monkeypatch.setattr(
        "app.services.image.image_understanding_service.ResourceBudgetService.execution_guidance",
        lambda self: {"defer_optional_heavy_media_work": False, "resource_pressure": "normal"},
    )
    result = ImageUnderstandingService(provider=FakeVisionProvider()).analyze(PNG_HEADER, "Read this image")
    assert result == {
        "success": True,
        "description": "A test image with readable text.",
        "model": "test-model",
    }


def test_image_analysis_route_returns_description(monkeypatch):
    class FakeService:
        provider_scope = "local"
        def analyze(self, image_bytes, prompt, *, save_artifact=False):
            assert image_bytes == PNG_HEADER
            assert prompt == "Read this image"
            assert save_artifact is False
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
        provider_scope = "local"
        def analyze(self, image_bytes, prompt, *, save_artifact=False):
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


def test_image_analysis_can_save_a_report_without_saving_original_image(monkeypatch):
    import hashlib
    import json

    class FakeArtifacts:
        def __init__(self):
            self.saved = None

        def create_artifact(self, artifact_type, content, source, extension):
            self.saved = {
                "type": artifact_type,
                "content": content,
                "source": source,
                "extension": extension,
            }
            return {
                "artifact_id": "report-123",
                "type": artifact_type,
                "timestamp": "2026-10-26T00:00:00+00:00",
            }

    monkeypatch.setattr(
        "app.services.image.image_understanding_service.ResourceBudgetService.execution_guidance",
        lambda self: {"defer_optional_heavy_media_work": False, "resource_pressure": "normal"},
    )
    artifacts = FakeArtifacts()
    service = ImageUnderstandingService(provider=FakeVisionProvider(), artifacts=artifacts)
    result = service.analyze(PNG_HEADER, "Read this image", save_artifact=True)

    assert result["success"] is True
    assert result["artifact_saved"] is True
    assert result["artifact"] == {
        "artifact_id": "report-123",
        "artifact_type": "reports",
        "created_at": "2026-10-26T00:00:00+00:00",
    }
    assert artifacts.saved["type"] == "reports"
    assert artifacts.saved["source"] == "image_understanding"
    assert artifacts.saved["extension"] == "json"
    report = json.loads(artifacts.saved["content"])
    assert report["description"] == "A test image with readable text."
    assert report["image_sha256"] == hashlib.sha256(PNG_HEADER).hexdigest()
    assert "image_bytes" not in report


def test_image_analysis_keeps_result_when_artifact_storage_fails(monkeypatch):
    class BrokenArtifacts:
        def create_artifact(self, *args, **kwargs):
            raise OSError("local disk detail must not leak")

    monkeypatch.setattr(
        "app.services.image.image_understanding_service.ResourceBudgetService.execution_guidance",
        lambda self: {"defer_optional_heavy_media_work": False, "resource_pressure": "normal"},
    )
    result = ImageUnderstandingService(
        provider=FakeVisionProvider(),
        artifacts=BrokenArtifacts(),
    ).analyze(PNG_HEADER, "Read this image", save_artifact=True)

    assert result["success"] is True
    assert result["description"] == "A test image with readable text."
    assert result["artifact_saved"] is False
    assert "local disk detail" not in result["artifact_warning"]


def test_image_analysis_route_reports_resource_pressure_as_temporary_unavailable(monkeypatch):
    class DeferredService:
        provider_scope = "local"
        def analyze(self, image_bytes, prompt, *, save_artifact=False):
            return {
                "success": False,
                "state": "deferred",
                "code": "resource_pressure_deferred",
                "message": "Image analysis was deferred because available system memory is constrained.",
            }

    monkeypatch.setattr(route, "ImageUnderstandingService", DeferredService)
    request = route.ImageAnalysisRequest(image_base64=base64.b64encode(PNG_HEADER).decode("ascii"))
    try:
        route.analyze_image(request)
    except HTTPException as exc:
        assert exc.status_code == 503
        assert exc.headers["Retry-After"] == "30"
    else:
        raise AssertionError("resource-pressure deferral must be a temporary unavailable response")


def test_image_analysis_can_use_saved_image_artifact(monkeypatch, tmp_path):
    image_path = tmp_path / "stored.png"
    image_path.write_bytes(PNG_HEADER)
    class FakeArtifacts:
        def get_artifact(self, artifact_id):
            return {"artifact_id": artifact_id, "type": "images", "archived": False} if artifact_id == "image-1" else None
        def get_artifact_path(self, artifact_id):
            return image_path if artifact_id == "image-1" else None
    class FakeService:
        provider_scope = "local"
        MAX_IMAGE_BYTES = 10_000_000
        def analyze(self, image_bytes, prompt, *, save_artifact=False):
            assert image_bytes == PNG_HEADER
            assert prompt == "Read the circuit labels"
            assert save_artifact is True
            return {"success": True, "description": "A labeled circuit", "artifact_saved": True}
    monkeypatch.setattr("app.services.artifacts.artifact_manager_service.ArtifactManagerService", FakeArtifacts)
    monkeypatch.setattr(route, "ImageUnderstandingService", FakeService)
    result = route.analyze_image_artifact(route.ImageArtifactAnalysisRequest(artifact_id="image-1", prompt="Read the circuit labels"))
    assert result["source_artifact_id"] == "image-1"
    assert result["description"] == "A labeled circuit"


def test_image_analysis_rejects_non_image_artifact(monkeypatch):
    class FakeArtifacts:
        def get_artifact(self, artifact_id):
            return {"artifact_id": artifact_id, "type": "reports", "archived": False}
    monkeypatch.setattr("app.services.artifacts.artifact_manager_service.ArtifactManagerService", FakeArtifacts)
    try:
        route.analyze_image_artifact(route.ImageArtifactAnalysisRequest(artifact_id="report-1"))
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("non-image artifact must be rejected")
