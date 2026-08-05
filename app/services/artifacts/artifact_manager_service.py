from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import json
import uuid

from app.services.memory.memory_service import (
    MemoryService
)

SUPPORTED_ARTIFACT_TYPES = {
    "audio",
    "transcripts",
    "summaries",
    "images",
    "diagrams",
    "blueprints",
    "schematics",
    "exports"
}


class ArtifactManagerService:

    def __init__(self):

        self.base_path = Path(
            "artifacts"
        )

        self.index_path = Path(
            "memory/artifact_index.json"
        )

        self.memory = (
            MemoryService()
        )

        self._ensure_storage()

    def _ensure_storage(self):

        artifact_types = [

            "audio",
            "transcripts",
            "summaries",
            "images",
            "diagrams",
            "blueprints",
            "schematics",
            "exports"
        ]

        self.base_path.mkdir(
            parents=True,
            exist_ok=True
        )

        for artifact_type in artifact_types:

            (
                self.base_path
                / artifact_type
            ).mkdir(
                parents=True,
                exist_ok=True
            )

        self.index_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.index_path.exists():

            self.index_path.write_text(
                json.dumps(
                    {
                        "artifacts": []
                    },
                    indent=2
                ),
                encoding="utf-8"
            )

    def _load_index(self):

        return json.loads(
            self.index_path.read_text(
                encoding="utf-8"
            )
        )

    def _save_index(
        self,
        data
    ):

        self.index_path.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    def create_artifact(
        self,
        artifact_type: str,
        content: str,
        source: str,
        extension: str = "txt"
    ) -> Dict[str, Any]:

        if artifact_type not in SUPPORTED_ARTIFACT_TYPES:

                    raise ValueError(
                        f"Unsupported artifact type: {artifact_type}"
                    )

        artifact_id = str(
            uuid.uuid4()
        )

        timestamp = (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        filename = (
            f"{artifact_id}.{extension}"
        )

        artifact_path = (
            self.base_path
            / artifact_type
            / filename
        )

        artifact_path.write_text(
            content,
            encoding="utf-8"
        )

        record = {

            "artifact_id":
            artifact_id,

            "type":
            artifact_type,

            "source":
            source,

            "file":
            str(
                artifact_path
            ),

            "timestamp":
            timestamp
        }

        index = self._load_index()

        index[
            "artifacts"
        ].append(
            record
        )

        self._save_index(
            index
        )

        self.memory.add_artifact(
            record
        )

        return record

    def get_artifact(
        self,
        artifact_id: str
    ):

        index = self._load_index()

        for artifact in index[
            "artifacts"
        ]:

            if artifact[
                "artifact_id"
            ] == artifact_id:

                return artifact

        return None

    def get_all_artifacts(
        self
    ):

        index = self._load_index()

        return index[
            "artifacts"
        ]

    def search(
        self,
        artifact_type: str = None
    ):

        artifacts = (
            self.get_all_artifacts()
        )

        if not artifact_type:

            return artifacts

        return [

            artifact

            for artifact
            in artifacts

            if artifact[
                "type"
            ] == artifact_type
        ]