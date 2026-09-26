from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException
)
from pydantic import BaseModel

from app.services.voice.voice_capture_service import (
    VoiceCaptureService
)
from app.services.voice.transcript_service import TranscriptService
from app.services.response.summary_service import SummaryService

router = APIRouter()


class ArtifactRequest(BaseModel):
    artifact_id: str


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

    extension = (

        audio.filename
        .split(".")[-1]
        .lower()
    )

    if extension not in allowed_extensions:

        raise HTTPException(

            status_code=400,

            detail=
            "Supported formats: wav, mp3, m4a"
        )

    result = (

        VoiceCaptureService()
        .save_audio(
            audio
        )
    )

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