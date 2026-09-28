from pathlib import Path
from datetime import datetime
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
        uploaded_file
    ):

        artifact_id = str(
            uuid.uuid4()
        )

        filename = getattr(uploaded_file, "filename", "") or ""
        extension = Path(filename).suffix.removeprefix(".").lower()
        if extension not in {"wav", "mp3", "m4a"}:
            raise ValueError("Supported formats: wav, mp3, m4a")

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
            with temporary_path.open("rb") as uploaded:
                signature = uploaded.read(12)
            if not self.artifacts._has_binary_signature("audio", signature, extension):
                raise ValueError("Audio upload content does not match its declared format signature")
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
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
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
