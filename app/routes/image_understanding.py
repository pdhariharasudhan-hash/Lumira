import base64
import binascii

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.image.image_understanding_service import ImageUnderstandingService

router = APIRouter()


class ImageAnalysisRequest(BaseModel):
    image_base64: str = Field(min_length=16, max_length=14_000_000)
    prompt: str = Field(default="Describe this image and extract any readable text.", min_length=1, max_length=4000)


@router.post("/images/analyze")
def analyze_image(request: ImageAnalysisRequest):
    try:
        image_bytes = base64.b64decode(request.image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="image_base64 must be valid Base64") from exc
    result = ImageUnderstandingService().analyze(image_bytes, request.prompt)
    if result.get("success") is True:
        return result
    code = result.get("code")
    if code == "provider_unavailable":
        raise HTTPException(status_code=503, detail=result["message"])
    if code in {"invalid_image", "invalid_prompt"}:
        raise HTTPException(status_code=422, detail=result["message"])
    raise HTTPException(status_code=502, detail=result.get("message", "Image analysis failed"))
