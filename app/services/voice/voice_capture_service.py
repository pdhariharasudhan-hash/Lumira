from pathlib import Path
from datetime import datetime, timezone
import os
import uuid

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService
)


class VoiceCaptureService:

    MAX_UPLOAD_BYTES = 25_000_000

    def __init__(self):

        self.audio_path = Path(
            "artifacts/audio"
        )

        self.audio_path.mkdir(
            parents=True,
            exist_ok=True
        )

        self.artifacts = (
            ArtifactManagerService()
        )

    def save_audio(
        self,
        uploaded_file,
        *,
        consent: dict | None = None,
    ):
        if not isinstance(consent, dict):
            raise ValueError("explicit voice capture and audio storage consent is required")
        retention = consent.get("retention")
        if not isinstance(retention, dict):
            raise ValueError("explicit audio retention consent is required")
        policy_consent = {
            "voice_capture": consent.get("voice_capture"),
            "audio_storage": consent.get("audio_storage"),
            "transcription": consent.get("transcription"),
            "receipt_id": consent.get("receipt_id"),
            "consented_at": consent.get("consented_at"),
            "retention_mode": retention.get("mode"),
            "retention_days": retention.get("days"),
        }

        artifact_id = str(
            uuid.uuid4()
        )

        filename = getattr(uploaded_file, "filename", "") or ""
        extension = Path(filename).suffix.removeprefix(".").lower()
        if extension not in {"wav", "mp3", "m4a", "ogg", "webm"}:
            raise ValueError("Supported formats: wav, mp3, m4a, ogg, webm")

        filename = (
            f"{artifact_id}.{extension}"
        )

        destination = (
            self.audio_path
            / filename
        )

        temporary_path = destination.with_name(f".{destination.name}.tmp")
        total_bytes = 0
        try:
            with temporary_path.open("wb") as buffer:
                while True:
                    chunk = uploaded_file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > self.MAX_UPLOAD_BYTES:
                        raise ValueError(f"Audio upload exceeds {self.MAX_UPLOAD_BYTES} bytes")
                    buffer.write(chunk)
            if total_bytes == 0:
                raise ValueError("Audio upload is empty")
            from app.services.voice.voice_capture_policy_service import VoiceCapturePolicyService
            decision = VoiceCapturePolicyService().evaluate(
                filename=getattr(uploaded_file, "filename", "") or "",
                size_bytes=total_bytes,
                consent=policy_consent,
            )
            if decision.get("allowed") is not True:
                raise ValueError(
                    "Audio capture policy rejected the upload: "
                    + str(decision.get("code", "consent_invalid"))
                )
            if decision.get("consent_receipt_id") != consent.get("receipt_id"):
                raise ValueError("Audio capture consent receipt could not be verified")
            with temporary_path.open("rb") as uploaded:
                signature = uploaded.read(12)
            if not self.artifacts._has_binary_signature("audio", signature, extension):
                raise ValueError("Audio upload content does not match its declared format signature")
            quality_analysis = None
            if extension == "wav":
                from app.services.voice.audio_quality_service import AudioQualityService
                quality_analysis = AudioQualityService().analyze_path(temporary_path)
            os.replace(temporary_path, destination)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

        record = {

            "artifact_id":
            artifact_id,

            "type":
            "audio",

            "source":
            "voice_capture",

            "file":
            str(
                destination
            ),

            "timestamp":
            datetime.now(timezone.utc).isoformat(),
            **({"consent": consent} if consent is not None else {}),
            **({"quality_analysis": quality_analysis} if quality_analysis is not None else {}),
        }

        try:
            self.artifacts.register_artifact(record)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        return {

            "success":
            True,

            "artifact":
            record
        }
