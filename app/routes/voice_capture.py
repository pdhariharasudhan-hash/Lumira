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
from app.services.memory.memory_service import MemoryService
from app.services.voice.wake_word_listener_service import WakeWordListenerService

router = APIRouter()
_wake_word_listener = WakeWordListenerService()


def _raise_for_voice_readiness(result: dict) -> None:
    """Map missing providers and resource-pressure deferrals to retryable HTTP errors."""
    code = result.get("code") if isinstance(result, dict) else None
    if code not in {"provider_unavailable", "resource_pressure_deferred"}:
        return
    headers = {"Retry-After": "30"} if code == "resource_pressure_deferred" else None
    raise HTTPException(status_code=501 if code == "provider_unavailable" else 503, detail=result, headers=headers)


class ArtifactRequest(BaseModel):
    artifact_id: str = Field(min_length=1, max_length=128)


class VoiceCoreProcessRequest(BaseModel):
    audio_artifact_id: str = Field(min_length=1, max_length=128)
    project_id: str | None = Field(default=None, max_length=100)
    goal_id: str | None = Field(default=None, max_length=128)


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
        "m4a",
        "ogg",
        "webm",
    }

    extension = (audio.filename or "").rsplit(".", 1)[-1].lower()

    if extension not in allowed_extensions:

        raise HTTPException(

            status_code=400,

            detail=
            "Supported formats: wav, mp3, m4a, ogg, webm"
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


@router.post("/voice/core-process")
def process_voice_through_core(request: VoiceCoreProcessRequest):
    from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService
    result = VoiceIdeaPipelineService().process(
        request.audio_artifact_id,
        project_id=request.project_id,
        goal_id=request.goal_id,
    )
    _raise_for_voice_readiness(result)
    return result


@router.post("/voice/transcript")
def transcribe_voice(request: ArtifactRequest):
    result = TranscriptService().generate_transcript(request.artifact_id)
    _raise_for_voice_readiness(result)
    return result


@router.post("/voice/summary")
def summarize_voice(request: ArtifactRequest):
    result = SummaryService().generate_summary(request.artifact_id)
    _raise_for_voice_readiness(result)
    return result


@router.post("/voice/activation")
def activate_voice(request: ArtifactRequest):
    from app.services.voice.voice_interaction_service import WakeWordActivationService

    result = WakeWordActivationService().activate(request.artifact_id)
    _raise_for_voice_readiness(result)
    if not result["success"] and result.get("code") == "audio_artifact_not_found":
        raise HTTPException(status_code=404, detail=result)
    return result


@router.get("/voice/artifacts/{artifact_id}/availability")
def voice_artifact_availability(artifact_id: str):
    from app.services.voice.audio_playback_service import AudioPlaybackService
    result = AudioPlaybackService().resolve(artifact_id)
    if not result.get("success"):
        status = 404 if result.get("code") in {"audio_not_found", "audio_unavailable"} else 422
        raise HTTPException(status_code=status, detail=result)
    return {"success": True, "artifact_id": artifact_id, "available": True}


@router.post("/voice/playback")
def playback_voice(request: PlaybackRequest):
    from app.services.voice.voice_interaction_service import SpeechPlaybackService

    result = SpeechPlaybackService().play(request.text, request.language)
    _raise_for_voice_readiness(result)
    if not result["success"] and result.get("code") == "invalid_request":
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/voice/wake-word/start")
def start_wake_word_listener():
    result = _wake_word_listener.start()
    if not result["success"] and result.get("code") == "provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    return result


@router.post("/voice/wake-word/stop")
def stop_wake_word_listener():
    result = _wake_word_listener.stop()
    if not result["success"]:
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/voice/wake-word/status")
def get_wake_word_listener_status():
    return _wake_word_listener.status()

@router.post("/voice/wake-word/consume")
def consume_wake_word_activation():
    """Hand one background wake-word activation to the main Lumira runtime."""
    result = _wake_word_listener.consume_activation()
    if result.get("activated"):
        event = result.get("event") if isinstance(result.get("event"), dict) else {}
        result["main_core"] = event.get("core_context", {})
    return result


class VoiceProcessRequest(BaseModel):
    audio_artifact_id: str = Field(min_length=1, max_length=128)
    generate_summary: bool = True


def _persist_voice_capture_memory(audio_artifact_id: str, transcript_artifact_id: str, transcription: dict, summary: dict | None = None) -> dict:
    """Persist a voice idea as an unverified memory experience without breaking artifact capture."""
    try:
        memory = MemoryService()
        existing = memory.get_all()
        experiences = existing.get("experiences", []) if isinstance(existing, dict) else []
        for item in experiences if isinstance(experiences, list) else []:
            ids = item.get("artifact_ids", []) if isinstance(item, dict) else []
            if isinstance(item, dict) and isinstance(ids, list) and audio_artifact_id in ids:
                return {"success": True, "state": "already_exists", "experience_id": item.get("experience_id"), "message": "This voice capture is already linked to memory."}

        transcript_text = transcription.get("transcript_text", "")
        transcript_text = transcript_text.strip() if isinstance(transcript_text, str) else ""
        summary_text = summary.get("summary_text", "") if isinstance(summary, dict) else ""
        summary_text = summary_text.strip() if isinstance(summary_text, str) else ""
        memory_summary = (summary_text or transcript_text).strip()
        if not memory_summary:
            return {"success": False, "code": "memory_content_unavailable", "message": "Voice artifacts were saved, but no text was available to store in memory."}

        artifact_ids = [audio_artifact_id, transcript_artifact_id]
        summary_record = summary.get("summary_artifact") if isinstance(summary, dict) else None
        summary_id = summary_record.get("artifact_id") if isinstance(summary_record, dict) else None
        if isinstance(summary_id, str) and summary_id.strip():
            artifact_ids.append(summary_id)
        record = memory.record_experience(
            experience_type="workflow",
            summary=memory_summary[:4000],
            outcome="Voice capture transcribed and stored. Summary: " + ("available" if summary_text else "not available"),
            artifact_ids=artifact_ids,
            lessons=[],
            verified=False,
        )
        return {"success": True, "state": "saved", "experience_id": record.get("experience_id"), "message": "Voice idea saved to memory and linked to its artifacts."}
    except Exception:
        # Memory is a downstream sink; never discard the already-saved audio/transcript.
        return {"success": False, "code": "memory_persistence_failed", "message": "Voice artifacts are preserved, but memory persistence did not complete. Retry from the saved artifacts."}




@router.get("/voice/idea-pipeline/{artifact_id}/status")
def voice_pipeline_status(artifact_id: str):
    from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService
    return VoiceIdeaPipelineService().inspect(artifact_id)


class VoiceIdeaPipelineRequest(BaseModel):
    audio_artifact_id: str = Field(min_length=1, max_length=128)
    project_id: str | None = Field(default=None, max_length=128)
    goal_id: str | None = Field(default=None, max_length=128)


@router.post("/voice/idea-pipeline/linked")
def process_linked_voice_idea_pipeline(request: VoiceIdeaPipelineRequest):
    from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService
    result = VoiceIdeaPipelineService().process(request.audio_artifact_id, request.project_id, request.goal_id)
    _raise_for_voice_readiness(result)
    if not result.get("success") and result.get("stage") == "validate":
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/voice/idea-pipeline")
def process_voice_idea_pipeline(request: ArtifactRequest):
    """Run the canonical voice idea pipeline with transcript, summary and memory."""
    from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService

    result = VoiceIdeaPipelineService().process(request.artifact_id)
    _raise_for_voice_readiness(result)
    if not result.get("success") and result.get("stage") == "validate":
        raise HTTPException(status_code=422, detail=result)
    return result

@router.post("/voice/process")
def process_voice_capture(request: VoiceProcessRequest):
    """Run the stored-audio -> transcript -> optional summary artifact workflow."""
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    artifacts = ArtifactManagerService()
    audio = artifacts.get_artifact(request.audio_artifact_id)
    if not audio or audio.get("type") != "audio":
        raise HTTPException(status_code=404, detail="audio artifact not found")

    transcript = TranscriptService().generate_transcript(request.audio_artifact_id)
    result = {
        "success": False,
        "audio_artifact_id": request.audio_artifact_id,
        "transcription": transcript,
        "summary": None,
        "stage": "transcription",
    }
    if not transcript.get("success"):
        result["message"] = "Audio is saved, but transcription did not complete. The audio artifact is preserved."
        return result

    transcript_record = transcript.get("transcript_artifact")
    transcript_id = transcript_record.get("artifact_id") if isinstance(transcript_record, dict) else None
    if not isinstance(transcript_id, str) or not transcript_id.strip():
        result["stage"] = "transcription_storage"
        result["message"] = "Transcription returned success without a usable transcript artifact identifier. The audio artifact is preserved."
        return result

    result["transcript_artifact_id"] = transcript_id
    result["stage"] = "transcription_complete"
    if not request.generate_summary:
        result["memory"] = _persist_voice_capture_memory(request.audio_artifact_id, transcript_id, transcript)
        result["success"] = True
        result["stage"] = "completed"
        result["message"] = "Audio and transcript artifacts are ready."
        return result

    summary = SummaryService().generate_summary(transcript_id)
    result["summary"] = summary
    result["memory"] = _persist_voice_capture_memory(request.audio_artifact_id, transcript_id, transcript, summary)
    if summary.get("success"):
        summary_record = summary.get("summary_artifact")
        summary_id = summary_record.get("artifact_id") if isinstance(summary_record, dict) else None
        if not isinstance(summary_id, str) or not summary_id.strip():
            result["stage"] = "summary_storage"
            result["message"] = "Summary generation reported success without a usable summary artifact identifier. The audio and transcript artifacts are preserved."
            return result
        result["summary_artifact_id"] = summary_id
        result["success"] = True
        result["stage"] = "completed"
        result["message"] = "Audio, transcript, and summary artifacts are ready."
    else:
        result["stage"] = "summary"
        result["message"] = "Audio and transcript are saved, but summary generation did not complete. Existing artifacts are preserved."
    return result



class VoicePipelineSummaryRetryRequest(BaseModel):
    transcript_artifact_id: str = Field(min_length=1, max_length=128)


@router.post("/voice/idea-pipeline/retry-summary")
def retry_pipeline_summary(request: VoicePipelineSummaryRetryRequest):
    from app.services.voice.voice_idea_pipeline_service import VoiceIdeaPipelineService
    result = VoiceIdeaPipelineService().retry_summary(request.transcript_artifact_id)
    _raise_for_voice_readiness(result)
    if not result.get("success") and result.get("code") == "invalid_transcript_artifact":
        raise HTTPException(status_code=422, detail=result)
    return result


class VoiceSummaryRetryRequest(BaseModel):
    transcript_artifact_id: str = Field(min_length=1, max_length=128)


@router.post("/voice/retry-summary")
def retry_voice_summary(request: VoiceSummaryRetryRequest):
    """Retry summarization from an existing transcript without uploading audio again."""
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    artifacts = ArtifactManagerService()
    transcript = artifacts.get_artifact(request.transcript_artifact_id)
    if not transcript or transcript.get("type") != "transcripts":
        raise HTTPException(status_code=404, detail="transcript artifact not found")

    transcript_path = artifacts.get_artifact_path(request.transcript_artifact_id)
    if transcript_path is None or not transcript_path.is_file():
        raise HTTPException(status_code=404, detail="transcript content not found")

    try:
        if transcript_path.stat().st_size > artifacts.MAX_CONTENT_LENGTH:
            raise HTTPException(status_code=413, detail="transcript exceeds the processing limit")
        transcript_text = transcript_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as error:
        raise HTTPException(status_code=422, detail="transcript content could not be read") from error
    if not transcript_text:
        raise HTTPException(status_code=422, detail="transcript is empty")

    result = SummaryService().generate_summary(request.transcript_artifact_id)
    if not result.get("success"):
        return {
            "success": False,
            "state": result.get("state", "failed"),
            "code": result.get("code", "summary_failed"),
            "transcript_artifact_id": request.transcript_artifact_id,
            "summary": result,
            "message": result.get("message", "Summary generation did not complete. The transcript artifact is preserved."),
        }

    summary_record = result.get("summary_artifact")
    summary_id = summary_record.get("artifact_id") if isinstance(summary_record, dict) else None
    if not isinstance(summary_id, str) or not summary_id.strip():
        return {
            "success": False,
            "state": "failed",
            "code": "summary_storage",
            "transcript_artifact_id": request.transcript_artifact_id,
            "message": "Summary generation reported success without a usable artifact ID. The transcript is preserved.",
        }
    try:
        memory_record = MemoryService().attach_artifacts_to_experience(request.transcript_artifact_id, [summary_id])
        memory_status = {"success": True, "state": "updated", "experience_id": memory_record.get("experience_id"), "message": "Summary artifact linked to the existing voice memory."}
    except KeyError:
        memory_status = {"success": True, "state": "not_linked", "message": "Summary created. No existing voice memory record matched this transcript."}
    except Exception:
        memory_status = {"success": False, "code": "memory_update_failed", "message": "Summary was saved, but the existing memory record could not be updated."}
    return {
        "success": True,
        "state": "completed",
        "transcript_artifact_id": request.transcript_artifact_id,
        "summary_artifact_id": summary_id,
        "summary": result,
        "memory": memory_status,
        "message": "Summary created from the existing transcript.",
    }


class VoiceResultSaveRequest(BaseModel):
    audio_artifact_id: str = Field(min_length=1, max_length=128)
    transcript_artifact_id: str | None = Field(default=None, max_length=128)
    summary_artifact_id: str | None = Field(default=None, max_length=128)


@router.post("/sessions/{session_id}/voice-result")
def save_voice_result(session_id: str, request: VoiceResultSaveRequest):
    """Persist a captured voice result in the owning conversation using stored artifacts."""
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService
    from app.services.sessions.session_manager_service import SessionManagerService

    sessions = SessionManagerService()
    if sessions.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    artifacts = ArtifactManagerService()
    audio = artifacts.get_artifact(request.audio_artifact_id)
    if not audio or audio.get("type") != "audio":
        raise HTTPException(status_code=404, detail="audio artifact not found")

    linked_ids = [request.audio_artifact_id]
    sections = ["Voice capture saved."]
    if not request.transcript_artifact_id:
        sections.append("Transcription unavailable or not configured.")
    elif not request.summary_artifact_id:
        sections.append("Summary unavailable or not configured.")
    metadata = {"voice_capture": {"audio_artifact_id": request.audio_artifact_id}}

    for artifact_id, expected_type, label, metadata_key in (
        (request.transcript_artifact_id, "transcripts", "Transcript", "transcript_artifact_id"),
        (request.summary_artifact_id, "summaries", "Summary", "summary_artifact_id"),
    ):
        if not artifact_id:
            continue
        record = artifacts.get_artifact(artifact_id)
        if not record or record.get("type") != expected_type:
            raise HTTPException(status_code=404, detail=f"{label.lower()} artifact not found")
        expected_source = request.audio_artifact_id if expected_type == "transcripts" else request.transcript_artifact_id
        if not expected_source or record.get("source") != expected_source:
            raise HTTPException(status_code=409, detail=f"{label} artifact does not belong to this voice capture")
        path = artifacts.get_artifact_path(artifact_id)
        if path is None or not path.is_file() or path.stat().st_size > artifacts.MAX_CONTENT_LENGTH:
            raise HTTPException(status_code=422, detail=f"{label} artifact is unavailable or exceeds the processing limit")
        try:
            content = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            raise HTTPException(status_code=422, detail=f"{label} artifact could not be read") from exc
        if not content:
            raise HTTPException(status_code=422, detail=f"{label} artifact is empty")
        sections.append(f"{label}:\n{content}")
        metadata["voice_capture"][metadata_key] = artifact_id
        linked_ids.append(artifact_id)

    for artifact_id in linked_ids:
        sessions.link_record(session_id, "artifact", artifact_id)
    message = sessions.append_message(
        session_id,
        "assistant",
        "\n\n".join(sections),
        metadata=metadata,
    )
    return {
        "success": True,
        "session_id": session_id,
        "message_id": message["message_id"],
        "linked_artifact_ids": linked_ids,
    }
