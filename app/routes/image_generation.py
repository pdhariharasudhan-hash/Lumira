from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.image.image_generation_service import ImageGenerationService

router = APIRouter()


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4_000)
    image_type: str = Field(default="image", pattern=r"^(image|diagram|blueprint|schematic)$")


@router.post("/images/generate")
def generate_image(request: ImageGenerationRequest):
    """Generate an image and persist successful output as an artifact."""
    result = ImageGenerationService().generate(request.prompt, request.image_type)
    if result.get("success"):
        return result

    code = result.get("code")
    if code in {"provider_unavailable", "resource_pressure_deferred"}:
        headers = {"Retry-After": "30"} if code == "resource_pressure_deferred" else None
        raise HTTPException(status_code=503, detail=result, headers=headers)
    if code in {
        "invalid_prompt",
        "invalid_provider_output",
        "invalid_provider_response",
        "image_size_limit_exceeded",
    }:
        raise HTTPException(status_code=422, detail=result)
    raise HTTPException(status_code=502, detail=result)
