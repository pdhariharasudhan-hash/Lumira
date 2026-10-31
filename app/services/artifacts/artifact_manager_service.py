from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any
import os
import re
import uuid

from app.services.memory.memory_service import (
    MemoryService
)
from app.services.persistence.atomic_json_store import (
    AtomicJsonStore,
    PersistenceIntegrityError,
)

SUPPORTED_ARTIFACT_TYPES = {
    "audio",
    "transcripts",
    "summaries",
    "images",
    "diagrams",
    "blueprints",
    "schematics",
    "exports",
    "reports",
    "video",
    "pdf",
    "generated_files",
}


class ArtifactManagerService:

    MAX_CONTENT_LENGTH = 1_000_000
    MAX_BINARY_CONTENT_BYTES = 25_000_000
    MAX_ARTIFACTS = 10_000
    BINARY_FORMATS = {
        "audio": {"wav", "mp3", "m4a", "ogg", "webm"},
        "images": {"png", "jpg", "jpeg", "webp"},
        "video": {"mp4", "webm"},
        "pdf": {"pdf"},
        "generated_files": {"zip"},
    }

    @staticmethod
    def _has_binary_signature(artifact_type: str, content: bytes, extension: str) -> bool:
        if artifact_type == "images":
            return {
                "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
                "jpg": content.startswith(b"\xff\xd8\xff"),
                "jpeg": content.startswith(b"\xff\xd8\xff"),
                "webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
            }.get(extension, False)
        if artifact_type == "audio":
            return {
                "wav": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE",
                "mp3": content.startswith(b"ID3") or (len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0),
                "m4a": len(content) >= 12 and content[4:8] == b"ftyp" and content[8:12] in {b"M4A ", b"isom", b"mp42"},
                "ogg": content.startswith(b"OggS"),
                "webm": content.startswith(b"\x1aE\xdf\xa3"),
            }.get(extension, False)
        if artifact_type == "video":
            return (extension == "mp4" and len(content) >= 12 and content[4:8] == b"ftyp") or (extension == "webm" and content.startswith(b"\x1aE\xdf\xa3"))
        if artifact_type == "pdf":
            return content.startswith(b"%PDF-")
        if artifact_type == "generated_files":
            return extension == "zip" and content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
        return False

    def __init__(self, base_path: str | Path = "artifacts", index_path: str | Path = "memory/artifact_index.json"):

        self.base_path = Path(base_path)

        self.index_path = Path(index_path)
        self.store = AtomicJsonStore(self.index_path)

        self.memory = (
            MemoryService()
        )

        self._ensure_storage()

    def _ensure_storage(self):

        artifact_types = sorted(SUPPORTED_ARTIFACT_TYPES)

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
            self.store.write({"artifacts": []})

    def _load_index(self):
        return self._validate_index(self.store.read({"artifacts": []}))

    def _validate_index(self, data):
        if not isinstance(data, dict) or not isinstance(data.get("artifacts"), list):
            raise PersistenceIntegrityError("Artifact index must contain an artifacts list")
        if len(data["artifacts"]) > ArtifactManagerService.MAX_ARTIFACTS:
            raise PersistenceIntegrityError("Artifact index exceeds the configured retention limit")
        required = {"artifact_id", "type", "source", "file", "timestamp"}
        for record in data["artifacts"]:
            if not isinstance(record, dict) or not required.issubset(record):
                raise PersistenceIntegrityError("Artifact index contains an incomplete record")
            try:
                record_size = len(__import__("json").dumps(record, ensure_ascii=False, allow_nan=False).encode("utf-8"))
            except (TypeError, ValueError, RecursionError) as exc:
                raise PersistenceIntegrityError("Artifact index record is not valid JSON") from exc
            if record_size > 20_000:
                raise PersistenceIntegrityError("Artifact index record exceeds the metadata size limit")
            if not isinstance(record["type"], str) or record["type"] not in SUPPORTED_ARTIFACT_TYPES:
                raise PersistenceIntegrityError("Artifact index contains an unsupported artifact type")
            if not all(isinstance(record[field], str) and record[field] for field in required):
                raise PersistenceIntegrityError("Artifact index contains invalid record fields")
            if (
                len(record["artifact_id"]) > 128
                or len(record["source"]) > 500
                or len(record["file"]) > 4096
                or len(record["timestamp"]) > 40
            ):
                raise PersistenceIntegrityError("Artifact index record fields exceed their limits")
            owner_id = record.get("owner_id", "local")
            if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 128:
                raise PersistenceIntegrityError("Artifact owner identifier is invalid")
            if "archived" in record and not isinstance(record["archived"], bool):
                raise PersistenceIntegrityError("Artifact archive state must be a boolean")
            for timestamp_field in ("archived_at", "restored_at"):
                if timestamp_field in record and (
                    not isinstance(record[timestamp_field], str)
                    or len(record[timestamp_field]) > 40
                ):
                    raise PersistenceIntegrityError("Artifact lifecycle timestamps are invalid")
        return data

    def _save_index(
        self,
        data
    ):

        self.store.write(self._validate_index(data))

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
        extension = extension.lower()
        if artifact_type in {"audio", "video", "pdf", "generated_files"}:
            raise ValueError(f"{artifact_type} artifacts must be created from validated binary content")
        if artifact_type == "images" and extension != "json":
            raise ValueError("Image specifications may be text JSON; rendered images require validated binary content")
        if not isinstance(content, str) or len(content) > self.MAX_CONTENT_LENGTH:
            raise ValueError(f"Artifact content must be at most {self.MAX_CONTENT_LENGTH} characters")
        if not isinstance(source, str) or len(source) > 500:
            raise ValueError("Artifact source must be at most 500 characters")

        artifact_id = str(
            uuid.uuid4()
        )

        timestamp = datetime.now(timezone.utc).isoformat()

        filename = (
            f"{artifact_id}.{extension}"
        )

        artifact_path = (
            self.base_path
            / artifact_type
            / filename
        )

        temporary_path = artifact_path.with_name(f".{artifact_path.name}.tmp")
        temporary_path.write_text(content, encoding="utf-8")
        os.replace(temporary_path, artifact_path)

        record = {

            "artifact_id":
            artifact_id,

            "owner_id":
            "local",

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

        try:
            self.register_artifact(record)
        except Exception:
            artifact_path.unlink(missing_ok=True)
            raise

        return record

    def register_artifact(self, record: dict) -> dict:
        record = dict(record)
        record.setdefault("owner_id", "local")
        record["source"] = self.memory._safe_text(record.get("source", ""))
        self._validate_index({"artifacts": [record]})
        path = Path(record["file"]).resolve()
        base = self.base_path.resolve()
        if path == base or base not in path.parents:
            raise ValueError("Artifact path is outside the artifact store")
        if not path.is_file():
            raise ValueError("Artifact content must exist inside the artifact store")

        def append_record(index):
            self._validate_index(index)
            if any(item["artifact_id"] == record["artifact_id"] for item in index["artifacts"]):
                raise PersistenceIntegrityError("Artifact identifier already exists")
            index["artifacts"].append(record)

        self.store.update(append_record, {"artifacts": []})
        self.memory.add_artifact(record)
        return record

    def create_binary_artifact(
        self,
        artifact_type: str,
        content: bytes,
        source: str,
        extension: str,
    ) -> dict:
        if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
            raise ValueError(f"Unsupported artifact type: {artifact_type}")
        if not isinstance(content, bytes) or not content or len(content) > self.MAX_BINARY_CONTENT_BYTES:
            raise ValueError(f"Binary artifact content must contain 1 to {self.MAX_BINARY_CONTENT_BYTES} bytes")
        if not re.fullmatch(r"[A-Za-z0-9]{1,12}", extension):
            raise ValueError("Artifact extension must be alphanumeric and 1-12 characters")
        if not isinstance(source, str) or len(source) > 500:
            raise ValueError("Artifact source must be at most 500 characters")
        extension = extension.lower()
        allowed_extensions = self.BINARY_FORMATS.get(artifact_type)
        if allowed_extensions is None or extension not in allowed_extensions:
            raise ValueError("Binary artifact type and extension are not supported")
        if not self._has_binary_signature(artifact_type, content, extension):
            raise ValueError("Binary artifact content does not match its declared format signature")

        artifact_id = str(uuid.uuid4())
        artifact_path = self.base_path / artifact_type / f"{artifact_id}.{extension}"
        temporary_path = artifact_path.with_name(f".{artifact_path.name}.tmp")
        temporary_path.write_bytes(content)
        os.replace(temporary_path, artifact_path)
        record = {
            "artifact_id": artifact_id,
            "owner_id": "local",
            "type": artifact_type,
            "source": source,
            "file": str(artifact_path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.register_artifact(record)
        except Exception:
            artifact_path.unlink(missing_ok=True)
            raise
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

    def archive_artifact(self, artifact_id: str) -> bool:
        """Mark an indexed artifact archived without deleting its file or index record."""
        now = datetime.now(timezone.utc).isoformat()
        archived = {"value": False, "at": None}

        def mark(index):
            self._validate_index(index)
            artifact = next((item for item in index["artifacts"] if item.get("artifact_id") == artifact_id), None)
            if artifact is None:
                return False
            if not artifact.get("archived", False):
                artifact["archived"] = True
                artifact["archived_at"] = now
            if not isinstance(artifact.get("archived_at"), str):
                artifact["archived_at"] = now
            archived["at"] = artifact["archived_at"]
            archived["value"] = True
            return True

        self.store.update(mark, {"artifacts": []})
        if archived["value"]:
            self.memory.update_artifact(artifact_id, {"archived": True, "archived_at": archived["at"]})
        return archived["value"]

    def restore_artifact(self, artifact_id: str) -> bool:
        """Restore an archived artifact without changing its stored content."""
        now = datetime.now(timezone.utc).isoformat()
        restored = {"value": False, "at": None}

        def mark(index):
            self._validate_index(index)
            artifact = next((item for item in index["artifacts"] if item.get("artifact_id") == artifact_id), None)
            if artifact is None:
                return False
            if artifact.get("archived", False):
                artifact["archived"] = False
                artifact["restored_at"] = now
            if not isinstance(artifact.get("restored_at"), str):
                artifact["restored_at"] = now
            restored["at"] = artifact["restored_at"]
            restored["value"] = True
            return True

        self.store.update(mark, {"artifacts": []})
        if restored["value"]:
            self.memory.update_artifact(artifact_id, {"archived": False})
        return restored["value"]

    def delete_artifact(self, artifact_id: str) -> bool:
        removed = {}

        def remove_record(index):
            self._validate_index(index)
            artifacts = index["artifacts"]
            artifact = next((item for item in artifacts if item.get("artifact_id") == artifact_id), None)
            if artifact is None:
                return False
            path = Path(artifact["file"]).resolve()
            base = self.base_path.resolve()
            if path == base or base not in path.parents:
                raise ValueError("Artifact path is outside the artifact store")
            removed["path"] = path
            removed["artifact"] = artifact
            index["artifacts"] = [item for item in artifacts if item.get("artifact_id") != artifact_id]
            return True

        deleted = self.store.update(remove_record, {"artifacts": []})
        artifact = removed.get("artifact")
        if artifact is None:
            return False

        path = removed["path"]
        if path.exists():
            path.unlink()
        self.memory.remove_artifact(artifact_id)
        return deleted

    def type_counts(self) -> dict:
        counts = {}
        for item in self.get_all_artifacts():
            key = item.get("type", "unknown")
            counts[key] = counts.get(key, 0) + 1
        return counts

    def recent_artifacts(self, limit: int = 20, include_archived: bool = False) -> list[dict]:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0 or limit > 100:
            raise ValueError("limit must be between 0 and 100")
        items = self.search(include_archived=include_archived)
        return sorted(items, key=lambda item: item.get("timestamp", ""), reverse=True)[:limit]

    def stats(self) -> dict:
        artifacts = self.get_all_artifacts()
        counts = {artifact_type: 0 for artifact_type in SUPPORTED_ARTIFACT_TYPES}
        active_counts = {artifact_type: 0 for artifact_type in SUPPORTED_ARTIFACT_TYPES}
        archived = 0
        for artifact in artifacts:
            artifact_type = artifact.get("type")
            if artifact_type in counts:
                counts[artifact_type] += 1
            if artifact.get("archived", False):
                archived += 1
            elif artifact_type in active_counts:
                active_counts[artifact_type] += 1
        return {
            "total": len(artifacts),
            "active": len(artifacts) - archived,
            "archived": archived,
            "by_type": counts,
            "active_by_type": active_counts,
        }

    def search(
        self,
        artifact_type: str = None,
        include_archived: bool = False,
    ):
        """Search active artifacts by default; include archived records only on request."""
        artifacts = self.get_all_artifacts()
        if not include_archived:
            artifacts = [item for item in artifacts if not item.get("archived", False)]

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
