from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException
)
from pydantic import BaseModel, Field

from app.services.voice.voice_capture_service import (
    VoiceCaptureService
)
from app.services.voice.transcript_service import TranscriptService
from app.services.response.summary_service import SummaryService

router = APIRouter()


class ArtifactRequest(BaseModel):
    artifact_id: str = Field(min_length=1, max_length=128)


class PlaybackRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1_000_000)
    language: str = Field(default="en", pattern=r"^(en|ta|ta-en)$")


@router.post(
    "/voice/upload"
)
async def upload_voice(

    audio: UploadFile = File(...)
):

    allowed_extensions = {

        "wav",
        "mp3",
        "m4a"
    }

    extension = (audio.filename or "").rsplit(".", 1)[-1].lower()

    if extension not in allowed_extensions:

        raise HTTPException(

            status_code=400,

            detail=
            "Supported formats: wav, mp3, m4a"
        )

    try:
        result = VoiceCaptureService().save_audio(audio)
    except ValueError as error:
        status = 413 if "exceeds" in str(error) else 400
        raise HTTPException(status_code=status, detail=str(error)) from error

    return {

        "success":
        True,

        "message":
        "Audio uploaded successfully",

        "data":
        result
    }


@router.post("/voice/transcript")
def transcribe_voice(request: ArtifactRequest):
    result = TranscriptService().generate_transcript(request.artifact_id)
    if not result["success"] and result.get("code") == "provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    return result


@router.post("/voice/summary")
def summarize_voice(request: ArtifactRequest):
    result = SummaryService().generate_summary(request.artifact_id)
    if not result["success"] and result.get("code") == "provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    return result


@router.post("/voice/activation")
def activate_voice(request: ArtifactRequest):
    from app.services.voice.voice_interaction_service import WakeWordActivationService

    result = WakeWordActivationService().activate(request.artifact_id)
    if not result["success"] and result.get("code") == "provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    if not result["success"] and result.get("code") == "audio_artifact_not_found":
        raise HTTPException(status_code=404, detail=result)
    return result


@router.post("/voice/playback")
def playback_voice(request: PlaybackRequest):
    from app.services.voice.voice_interaction_service import SpeechPlaybackService

    result = SpeechPlaybackService().play(request.text, request.language)
    if not result["success"] and result.get("code") == "provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    if not result["success"] and result.get("code") == "invalid_request":
        raise HTTPException(status_code=422, detail=result)
    return result
