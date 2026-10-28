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
    raise HTTPException(status_code=503, detail=result, headers=headers)


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
        raise HTTPException(status_code=503, detail=result)
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


def _link_voice_artifacts(artifacts, audio_artifact_id: str, transcript_artifact_id: str, summary_artifact_id: str | None = None) -> list[dict]:
    """Connect the stored audio, transcript, and optional summary without duplicating links."""
    specifications = [
        (audio_artifact_id, transcript_artifact_id, "transcribed_as"),
    ]
    if summary_artifact_id:
        specifications.append((transcript_artifact_id, summary_artifact_id, "summarized_as"))
    statuses = []
    for source_id, target_id, relation in specifications:
        try:
            statuses.append({
                **artifacts.link_artifacts(source_id, target_id, relation),
                "relation": relation,
                "source_artifact_id": source_id,
                "target_artifact_id": target_id,
            })
        except (KeyError, ValueError):
            # Artifact content remains useful even if the relationship index needs repair.
            statuses.append({
                "changed": False,
                "relation": relation,
                "source_artifact_id": source_id,
                "target_artifact_id": target_id,
                "state": "not_linked",
            })
    return statuses


class VoiceProcessRequest(BaseModel):
    audio_artifact_id: str = Field(min_length=1, max_length=128)
    generate_summary: bool = True


def _reuse_existing_voice_summary(artifacts, transcript_artifact_id: str) -> dict | None:
    """Reuse a saved summary for a transcript instead of duplicating artifacts on retry."""
    try:
        links = artifacts.get_artifact_links(transcript_artifact_id).get("links", [])
    except (KeyError, ValueError, OSError):
        return None

    for link in links if isinstance(links, list) else []:
        if not isinstance(link, dict):
            continue
        if link.get("direction") != "outgoing" or link.get("relation") != "summarized_as":
            continue
        summary_id = link.get("artifact_id")
        if not isinstance(summary_id, str) or not summary_id:
            continue
        record = artifacts.get_artifact(summary_id)
        if not record or record.get("type") != "summaries" or record.get("archived", False):
            continue
        if record.get("source") != transcript_artifact_id:
            continue
        try:
            path = artifacts.get_artifact_path(summary_id)
            if path is None or not path.is_file() or path.stat().st_size > artifacts.MAX_CONTENT_LENGTH:
                continue
            summary_text = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError, ValueError):
            continue
        if not summary_text:
            continue
        return {
            "success": True,
            "transcript_artifact": transcript_artifact_id,
            "summary_text": summary_text,
            "summary_artifact": record,
            "reused": True,
        }
    return None


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


def _reuse_existing_voice_transcript(artifacts, audio_artifact_id: str) -> dict | None:
    """Reuse a prior transcript for this audio so a retried pipeline is idempotent."""
    try:
        links = artifacts.get_artifact_links(audio_artifact_id).get("links", [])
    except (KeyError, ValueError, OSError):
        return None

    for link in links if isinstance(links, list) else []:
        if not isinstance(link, dict):
            continue
        if link.get("direction") != "outgoing" or link.get("relation") != "transcribed_as":
            continue
        transcript_id = link.get("artifact_id")
        if not isinstance(transcript_id, str) or not transcript_id:
            continue
        record = artifacts.get_artifact(transcript_id)
        if not record or record.get("type") != "transcripts" or record.get("archived", False):
            continue
        if record.get("source") != audio_artifact_id:
            continue
        try:
            path = artifacts.get_artifact_path(transcript_id)
            if path is None or not path.is_file() or path.stat().st_size > artifacts.MAX_CONTENT_LENGTH:
                continue
            transcript_text = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError, ValueError):
            continue
        if not transcript_text:
            continue
        from app.services.language.language_detection_service import LanguageDetectionService

        language = LanguageDetectionService().detect(transcript_text)
        return {
            "success": True,
            "audio_artifact": audio_artifact_id,
            "transcript_text": transcript_text,
            "transcript_artifact": record,
            "language": language.get("language", "unknown"),
            "language_confidence": language.get("confidence", 0),
            "reused": True,
        }
    return None


@router.post("/voice/process")
def process_voice_capture(request: VoiceProcessRequest):
    """Run the stored-audio -> transcript -> optional summary artifact workflow."""
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    artifacts = ArtifactManagerService()
    audio = artifacts.get_artifact(request.audio_artifact_id)
    if not audio or audio.get("type") != "audio":
        raise HTTPException(status_code=404, detail="audio artifact not found")

    transcript = _reuse_existing_voice_transcript(artifacts, request.audio_artifact_id)\n    if transcript is None:\n        transcript = TranscriptService().generate_transcript(request.audio_artifact_id)
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
    result["artifact_relationships"] = _link_voice_artifacts(artifacts, request.audio_artifact_id, transcript_id)
    result["stage"] = "transcription_complete"
    if not request.generate_summary:
        result["memory"] = _persist_voice_capture_memory(request.audio_artifact_id, transcript_id, transcript)
        result["success"] = True
        result["stage"] = "completed"
        result["message"] = "Audio and transcript artifacts are ready."
        return result

    summary = _reuse_existing_voice_summary(artifacts, transcript_id)
    if summary is None:
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
        result["artifact_relationships"] = _link_voice_artifacts(artifacts, request.audio_artifact_id, transcript_id, summary_id)
        result["success"] = True
        result["stage"] = "completed"
        result["message"] = "Audio, transcript, and summary artifacts are ready."
    else:
        result["stage"] = "summary"
        result["message"] = "Audio and transcript are saved, but summary generation did not complete. Existing artifacts are preserved."
    return result



class VoiceMemoryRetryRequest(BaseModel):
    audio_artifact_id: str = Field(min_length=1, max_length=128)
    transcript_artifact_id: str = Field(min_length=1, max_length=128)
    summary_artifact_id: str | None = Field(default=None, max_length=128)


@router.post("/voice/retry-memory")
def retry_voice_memory(request: VoiceMemoryRetryRequest):
    """Recover memory persistence from saved artifacts without re-recording or re-transcribing."""
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    artifacts = ArtifactManagerService()
    audio = artifacts.get_artifact(request.audio_artifact_id)
    transcript = artifacts.get_artifact(request.transcript_artifact_id)
    if not audio or audio.get("type") != "audio":
        raise HTTPException(status_code=404, detail="audio artifact not found")
    if not transcript or transcript.get("type") != "transcripts":
        raise HTTPException(status_code=404, detail="transcript artifact not found")
    if audio.get("archived", False) or transcript.get("archived", False):
        raise HTTPException(status_code=409, detail="archived voice artifacts cannot be used for memory recovery")
    if transcript.get("source") != request.audio_artifact_id:
        raise HTTPException(status_code=409, detail="transcript does not belong to the supplied audio artifact")

    transcript_path = artifacts.get_artifact_path(request.transcript_artifact_id)
    if transcript_path is None or not transcript_path.is_file():
        raise HTTPException(status_code=404, detail="transcript content not found")
    try:
        if transcript_path.stat().st_size > artifacts.MAX_CONTENT_LENGTH:
            raise HTTPException(status_code=413, detail="transcript exceeds the processing limit")
        transcript_text = transcript_path.read_text(encoding="utf-8").strip()
    except HTTPException:
        raise
    except (OSError, UnicodeError) as error:
        raise HTTPException(status_code=422, detail="transcript content could not be read") from error
    if not transcript_text:
        raise HTTPException(status_code=422, detail="transcript is empty")

    summary = None
    summary_text = ""
    if request.summary_artifact_id:
        summary_record = artifacts.get_artifact(request.summary_artifact_id)
        if not summary_record or summary_record.get("type") != "summaries":
            raise HTTPException(status_code=404, detail="summary artifact not found")
        if summary_record.get("archived", False):
            raise HTTPException(status_code=409, detail="archived summary artifacts cannot be used for memory recovery")
        if summary_record.get("source") != request.transcript_artifact_id:
            raise HTTPException(status_code=409, detail="summary does not belong to the supplied transcript")
        summary_path = artifacts.get_artifact_path(request.summary_artifact_id)
        if summary_path is None or not summary_path.is_file():
            raise HTTPException(status_code=404, detail="summary content not found")
        try:
            if summary_path.stat().st_size > artifacts.MAX_CONTENT_LENGTH:
                raise HTTPException(status_code=413, detail="summary exceeds the processing limit")
            summary_text = summary_path.read_text(encoding="utf-8").strip()
        except HTTPException:
            raise
        except (OSError, UnicodeError) as error:
            raise HTTPException(status_code=422, detail="summary content could not be read") from error
        if not summary_text:
            raise HTTPException(status_code=422, detail="summary is empty")
        summary = {
            "summary_text": summary_text,
            "summary_artifact": {"artifact_id": request.summary_artifact_id},
        }

    try:
        memory = MemoryService()
        existing = memory.get_all()
        experiences = existing.get("experiences", []) if isinstance(existing, dict) else []
        found = any(
            isinstance(item, dict)
            and isinstance(item.get("artifact_ids"), list)
            and request.audio_artifact_id in item["artifact_ids"]
            for item in (experiences if isinstance(experiences, list) else [])
        )
        if found:
            additions = [request.transcript_artifact_id]
            if request.summary_artifact_id:
                additions.append(request.summary_artifact_id)
            record = memory.attach_artifacts_to_experience(request.audio_artifact_id, additions)
            memory_result = {
                "success": True,
                "state": "updated",
                "experience_id": record.get("experience_id"),
                "message": "Saved voice artifacts were attached to the existing memory experience.",
            }
        else:
            memory_result = _persist_voice_capture_memory(
                request.audio_artifact_id,
                request.transcript_artifact_id,
                {"transcript_text": transcript_text},
                summary,
            )
    except Exception:
        memory_result = {
            "success": False,
            "code": "memory_persistence_failed",
            "message": "The saved voice artifacts remain available, but memory persistence could not be recovered.",
        }

    if memory_result.get("success") is not True:
        raise HTTPException(status_code=503, detail=memory_result)

    relationships = _link_voice_artifacts(
        artifacts,
        request.audio_artifact_id,
        request.transcript_artifact_id,
        request.summary_artifact_id,
    )
    return {
        "success": True,
        "state": "completed",
        "audio_artifact_id": request.audio_artifact_id,
        "transcript_artifact_id": request.transcript_artifact_id,
        "summary_artifact_id": request.summary_artifact_id,
        "artifact_relationships": relationships,
        "memory": memory_result,
        "message": "Saved voice artifacts are linked to Lumira memory.",
    }


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

    if transcript.get("archived", False):
        raise HTTPException(status_code=409, detail="archived transcript artifacts cannot be summarized")

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
    audio_id = transcript.get("source")
    audio_record = artifacts.get_artifact(audio_id) if isinstance(audio_id, str) else None
    relationships = _link_voice_artifacts(artifacts, audio_id, request.transcript_artifact_id, summary_id) if audio_record and audio_record.get("type") == "audio" else []
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
        "artifact_relationships": relationships,
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

    # Maintain a navigable artifact graph as well as the session's artifact links.
    artifact_relationships = []
    relationship_specs = []
    if request.transcript_artifact_id:
        relationship_specs.append((request.audio_artifact_id, request.transcript_artifact_id, "transcribed_as"))
    if request.transcript_artifact_id and request.summary_artifact_id:
        relationship_specs.append((request.transcript_artifact_id, request.summary_artifact_id, "summarized_as"))
    for source_id, target_id, relation in relationship_specs:
        try:
            artifact_relationships.append(
                artifacts.link_artifacts(source_id, target_id, relation)
            )
        except (KeyError, ValueError):
            # Keep the voice result available even if relationship metadata needs repair.
            artifact_relationships.append({
                "changed": False,
                "relation": relation,
                "source_artifact_id": source_id,
                "target_artifact_id": target_id,
                "state": "not_linked",
            })

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
        "artifact_relationships": artifact_relationships,
    }
