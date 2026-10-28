import base64
import binascii

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.image.image_understanding_service import ImageUnderstandingService

router = APIRouter()


class ImageAnalysisRequest(BaseModel):
    image_base64: str = Field(min_length=16, max_length=14_000_000)
    prompt: str = Field(default="Describe this image and extract any readable text.", min_length=1, max_length=4000)
    save_artifact: bool = Field(default=False, description="Save the analysis report locally; the original image is not stored.")


class ImageArtifactAnalysisRequest(BaseModel):
    artifact_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(default="Describe this image and extract any readable text.", min_length=1, max_length=4000)
    save_artifact: bool = False


@router.post("/images/analyze-artifact")
def analyze_image_artifact(request: ImageArtifactAnalysisRequest):
    """Analyze an image already stored in the artifact library."""
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    artifacts = ArtifactManagerService()
    image = artifacts.get_artifact(request.artifact_id)
    if image is None or image.get("type") != "images":
        raise HTTPException(status_code=404, detail="image artifact not found")
    if image.get("archived", False):
        raise HTTPException(status_code=409, detail="archived image artifacts cannot be analyzed")

    path = artifacts.get_artifact_path(request.artifact_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="image content not found")
    try:
        size = path.stat().st_size
        if size <= 0:
            raise HTTPException(status_code=422, detail="image content is empty")
        if size > ImageUnderstandingService.MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="image exceeds the 10 MB analysis limit")
        image_bytes = path.read_bytes()
    except HTTPException:
        raise
    except OSError as exc:
        raise HTTPException(status_code=422, detail="image content could not be read") from exc

    result = ImageUnderstandingService().analyze(
        image_bytes,
        request.prompt,
        save_artifact=request.save_artifact,
    )
    if result.get("success") is not True:
        code = result.get("code")
        if code in {"provider_unavailable", "resource_pressure_deferred"}:
            headers = {"Retry-After": "30"} if code == "resource_pressure_deferred" else None
            raise HTTPException(status_code=503, detail=result.get("message", "Image analysis is temporarily unavailable"), headers=headers)
        if code in {"invalid_image", "invalid_prompt"}:
            raise HTTPException(status_code=422, detail=result.get("message", "Invalid image analysis request"))
        raise HTTPException(status_code=502, detail=result.get("message", "Image analysis failed"))

    report = result.get("artifact")
    report_id = report.get("artifact_id") if isinstance(report, dict) else None
    if result.get("artifact_saved") is True and isinstance(report_id, str):
        try:
            result["artifact_relationship"] = artifacts.link_artifacts(
                request.artifact_id, report_id, "analyzed_as"
            )
        except (KeyError, ValueError):
            result["artifact_relationship"] = {"changed": False, "state": "not_linked"}
    result["source_artifact_id"] = request.artifact_id
    return result


@router.post("/images/analyze")
def analyze_image(request: ImageAnalysisRequest):
    try:
        image_bytes = base64.b64decode(request.image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="image_base64 must be valid Base64") from exc
    result = ImageUnderstandingService().analyze(
        image_bytes,
        request.prompt,
        save_artifact=request.save_artifact,
    )
    if result.get("success") is True:
        return result
    code = result.get("code")
    if code in {"provider_unavailable", "resource_pressure_deferred"}:
        # These are temporary readiness conditions, not malformed image input.
        headers = {"Retry-After": "30"} if code == "resource_pressure_deferred" else None
        raise HTTPException(status_code=503, detail=result["message"], headers=headers)
    if code in {"invalid_image", "invalid_prompt"}:
        raise HTTPException(status_code=422, detail=result["message"])
    raise HTTPException(status_code=502, detail=result.get("message", "Image analysis failed"))
