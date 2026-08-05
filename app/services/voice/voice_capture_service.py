from pathlib import Path
from datetime import datetime
import shutil
import uuid

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService
)


class VoiceCaptureService:

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

        extension = (
            uploaded_file.filename
            .split(".")[-1]
            .lower()
        )

        filename = (
            f"{artifact_id}.{extension}"
        )

        destination = (
            self.audio_path
            / filename
        )

        with open(
            destination,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                uploaded_file.file,
                buffer
            )

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

        index = (
            self.artifacts
            ._load_index()
        )

        index[
            "artifacts"
        ].append(
            record
        )

        self.artifacts._save_index(
            index
        )

        self.artifacts.memory.add_artifact(
            record
        )

        return {

            "success":
            True,

            "artifact":
            record
        }