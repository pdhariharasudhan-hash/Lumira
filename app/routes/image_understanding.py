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


class ImageArtifactAnalysisRequest(BaseModel):
    artifact_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(default="Describe this image and extract any readable text.", min_length=1, max_length=4000)
    save_artifact: bool = Field(default=True, description="Save the analysis report; the source image is already stored as an artifact.")


@router.post("/images/analyze-artifact")
def analyze_image_artifact(request: ImageArtifactAnalysisRequest):
    """Analyze an image already in Lumira's artifact library without re-uploading it."""
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    artifacts = ArtifactManagerService()
    artifact = artifacts.get_artifact(request.artifact_id)
    if artifact is None or artifact.get("archived", False):
        raise HTTPException(status_code=404, detail="active image artifact not found")
    if artifact.get("type") != "images":
        raise HTTPException(status_code=422, detail="artifact is not an image")
    try:
        path = artifacts.get_artifact_path(request.artifact_id)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="image artifact content not found")
        if path.stat().st_size > ImageUnderstandingService.MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="image artifact exceeds the 10 MB analysis limit")
        image_bytes = path.read_bytes()
    except HTTPException:
        raise
    except (OSError, ValueError):
        raise HTTPException(status_code=422, detail="image artifact content could not be read safely") from None

    result = ImageUnderstandingService().analyze(image_bytes, request.prompt, save_artifact=request.save_artifact)
    if result.get("success") is True:
        result["source_artifact_id"] = request.artifact_id
        return result
    code = result.get("code")
    if code in {"provider_unavailable", "resource_pressure_deferred"}:
        headers = {"Retry-After": "30"} if code == "resource_pressure_deferred" else None
        raise HTTPException(status_code=503, detail=result["message"], headers=headers)
    if code in {"invalid_image", "invalid_prompt"}:
        raise HTTPException(status_code=422, detail=result["message"])
    raise HTTPException(status_code=502, detail=result.get("message", "Image analysis failed"))
