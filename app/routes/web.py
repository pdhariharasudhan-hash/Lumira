from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.web.web_resource_service import WebResourceError, WebResourceService


router = APIRouter(prefix="/web", tags=["web"])
service = WebResourceService()


class WebResourceRequest(BaseModel):
    url: str = Field(min_length=8, max_length=4096)


@router.post("/fetch")
async def fetch_web_resource(request: WebResourceRequest):
    try:
        return await service.fetch(request.url)
    except WebResourceError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "unsafe_or_unavailable_url", "message": str(exc)},
        ) from exc
