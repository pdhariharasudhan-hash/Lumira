from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException
)

from app.services.voice_capture_service import (
    VoiceCaptureService
)

router = APIRouter()


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