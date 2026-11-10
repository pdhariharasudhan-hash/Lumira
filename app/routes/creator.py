from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.creator.creator_os_service import CreatorOSService

router = APIRouter(prefix="/creator", tags=["Creator OS"])
service = CreatorOSService()


class CreatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=160)
    brief: str = Field(min_length=1, max_length=12000)
    audience: str = Field(default="General", max_length=160)
    slides: list[str] | None = Field(default=None, max_length=30)


@router.get("/status")
def creator_status():
    return {"success": True, "capabilities": sorted(service.KINDS),
            "outputs": ["SVG poster/logo concepts", "HTML presentations", "JSON storyboards", "Markdown documents and scripts", "provider-backed MP3 narration", "provider-backed MP4/WebM video when configured"],
            "provider_media_rendering": "separate configured image/video providers are required for raster/video rendering"}


class CreatorAudioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=20000)
    language: str = Field(default="en", pattern=r"^(en|ta|ta-en)$")


@router.post("/audio")
def create_creator_audio(request: CreatorAudioRequest):
    try:
        result = service.synthesize_audio(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.get("code") == "speech_provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    if result.get("code") in {"external_provider_consent_required", "local_provider_blocked"}:
        raise HTTPException(status_code=403, detail=result)
    if result.get("code") in {"provider_policy_unavailable", "provider_policy_invalid"}:
        raise HTTPException(status_code=503, detail=result)
    if result.get("code") == "speech_provider_error":
        raise HTTPException(status_code=503, detail=result)
    if result.get("success") is not True:
        raise HTTPException(status_code=502, detail=result)
    return result


class CreatorVideoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=12000)
    duration_seconds: int = Field(default=5, ge=1, le=60)
    aspect_ratio: str = Field(default="16:9", pattern=r"^(16:9|9:16|1:1)$")


@router.post("/video")
def create_creator_video(request: CreatorVideoRequest):
    try:
        result = service.generate_video(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.get("code") == "video_provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    if result.get("code") in {"external_provider_consent_required", "local_provider_blocked"}:
        raise HTTPException(status_code=403, detail=result)
    if result.get("success") is not True:
        raise HTTPException(status_code=503, detail=result)
    return result


@router.post("/create")
def create_creator_artifact(request: CreatorRequest):
    try:
        return service.create(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Creator artifact could not be stored") from exc
