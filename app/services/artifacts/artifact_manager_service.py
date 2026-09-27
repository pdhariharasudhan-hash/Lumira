from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import json
import re
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
        if not re.fullmatch(r"[A-Za-z0-9]{1,12}", extension):
            raise ValueError("Artifact extension must be alphanumeric and 1-12 characters")

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

    def get_artifact_path(self, artifact_id: str) -> Path | None:
        artifact = self.get_artifact(artifact_id)
        if artifact is None:
            return None

        path = Path(artifact["file"]).resolve()
        base = self.base_path.resolve()
        if path == base or base not in path.parents:
            raise ValueError("Artifact path is outside the artifact store")
        return path

    def delete_artifact(self, artifact_id: str) -> bool:
        index = self._load_index()
        artifacts = index.get("artifacts", [])
        artifact = next(
            (
                item
                for item in artifacts
                if item.get("artifact_id") == artifact_id
            ),
            None,
        )
        if artifact is None:
            return False

        path = self.get_artifact_path(artifact_id)
        if path and path.exists():
            path.unlink()

        index["artifacts"] = [
            item
            for item in artifacts
            if item.get("artifact_id") != artifact_id
        ]
        self._save_index(index)
        self.memory.remove_artifact(artifact_id)
        return True

    def stats(self) -> dict:
        artifacts = self.get_all_artifacts()
        counts = {artifact_type: 0 for artifact_type in SUPPORTED_ARTIFACT_TYPES}
        for artifact in artifacts:
            artifact_type = artifact.get("type")
            if artifact_type in counts:
                counts[artifact_type] += 1
        return {"total": len(artifacts), "by_type": counts}

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