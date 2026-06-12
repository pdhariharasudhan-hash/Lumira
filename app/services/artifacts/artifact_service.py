from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4


class ArtifactService:
    """
    Central artifact manager.

    Stores:
        artifacts/
            images/
            audio/
            code/
            docs/
            metadata.json
    """

    BASE_DIR = Path("artifacts")
    METADATA_FILE = BASE_DIR / "metadata.json"

    ARTIFACT_TYPES = {
        "images",
        "audio",
        "code",
        "docs",
    }

    def __init__(self):
        self.BASE_DIR.mkdir(exist_ok=True)

        for artifact_type in self.ARTIFACT_TYPES:
            (self.BASE_DIR / artifact_type).mkdir(
                parents=True,
                exist_ok=True,
            )

        if not self.METADATA_FILE.exists():
            self._save_metadata({})

    # --------------------------------------------------
    # Metadata Helpers
    # --------------------------------------------------

    def _load_metadata(self) -> dict:
        try:
            with open(self.METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_metadata(self, data: dict) -> None:
        with open(self.METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # --------------------------------------------------
    # Create
    # --------------------------------------------------

    def create_artifact(
        self,
        artifact_type: str,
        content: str,
        extension: str = "txt",
        source: str = "system",
    ) -> dict:
        """
        Create artifact from text content.
        """

        if artifact_type not in self.ARTIFACT_TYPES:
            raise ValueError(
                f"Invalid artifact type: {artifact_type}"
            )

        artifact_id = str(uuid4())

        filename = f"{artifact_id}.{extension}"

        artifact_path = (
            self.BASE_DIR
            / artifact_type
            / filename
        )

        with open(
            artifact_path,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(content)

        metadata = self._load_metadata()

        metadata[artifact_id] = {
            "artifact_id": artifact_id,
            "type": artifact_type,
            "source": source,
            "file": str(artifact_path),
            "created": datetime.utcnow().isoformat(),
        }

        self._save_metadata(metadata)

        return metadata[artifact_id]

    # --------------------------------------------------
    # Create From Existing File
    # --------------------------------------------------

    def register_file(
        self,
        file_path: str,
        artifact_type: str,
        source: str = "external",
    ) -> dict:

        if artifact_type not in self.ARTIFACT_TYPES:
            raise ValueError(
                f"Invalid artifact type: {artifact_type}"
            )

        src = Path(file_path)

        if not src.exists():
            raise FileNotFoundError(file_path)

        artifact_id = str(uuid4())

        dst = (
            self.BASE_DIR
            / artifact_type
            / f"{artifact_id}{src.suffix}"
        )

        shutil.copy(src, dst)

        metadata = self._load_metadata()

        metadata[artifact_id] = {
            "artifact_id": artifact_id,
            "type": artifact_type,
            "source": source,
            "file": str(dst),
            "created": datetime.utcnow().isoformat(),
        }

        self._save_metadata(metadata)

        return metadata[artifact_id]

    # --------------------------------------------------
    # Read
    # --------------------------------------------------

    def get_artifact(
        self,
        artifact_id: str,
    ) -> Optional[dict]:

        metadata = self._load_metadata()

        return metadata.get(artifact_id)

    def get_artifact_content(
        self,
        artifact_id: str,
    ) -> Optional[str]:

        artifact = self.get_artifact(
            artifact_id
        )

        if not artifact:
            return None

        file_path = Path(
            artifact["file"]
        )

        if not file_path.exists():
            return None

        return file_path.read_text(
            encoding="utf-8"
        )

    # --------------------------------------------------
    # Delete
    # --------------------------------------------------

    def delete_artifact(
        self,
        artifact_id: str,
    ) -> bool:

        metadata = self._load_metadata()

        artifact = metadata.get(
            artifact_id
        )

        if not artifact:
            return False

        file_path = Path(
            artifact["file"]
        )

        if file_path.exists():
            file_path.unlink()

        metadata.pop(
            artifact_id,
            None,
        )

        self._save_metadata(metadata)

        return True

    # --------------------------------------------------
    # List
    # --------------------------------------------------

    def list_artifacts(
        self,
        artifact_type: str | None = None,
    ) -> list:

        metadata = self._load_metadata()

        results = []

        for artifact in metadata.values():

            if (
                artifact_type
                and artifact["type"]
                != artifact_type
            ):
                continue

            results.append(artifact)

        return sorted(
            results,
            key=lambda x: x["created"],
            reverse=True,
        )

    # --------------------------------------------------
    # Search
    # --------------------------------------------------

    def search_artifacts(
        self,
        query: str,
    ) -> list:

        metadata = self._load_metadata()

        results = []

        query = query.lower()

        for artifact in metadata.values():

            if (
                query
                in json.dumps(
                    artifact
                ).lower()
            ):
                results.append(
                    artifact
                )

        return results

    # --------------------------------------------------
    # Stats
    # --------------------------------------------------

    def stats(self) -> dict:

        metadata = self._load_metadata()

        counts = {
            t: 0
            for t in self.ARTIFACT_TYPES
        }

        for artifact in metadata.values():
            counts[
                artifact["type"]
            ] += 1

        return {
            "total": len(metadata),
            "by_type": counts,
        }