from typing import Any

from app.services.artifacts.artifact_manager_service import ArtifactManagerService, SUPPORTED_ARTIFACT_TYPES


class ArtifactLibraryQueryService:
    """Bounded filtering and pagination for artifact-library consumers."""

    def __init__(self, manager: ArtifactManagerService | None = None) -> None:
        self.manager = manager or ArtifactManagerService()

    def list_artifacts(self, *, artifact_type: str | None = None, query: str | None = None, include_archived: bool = False, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        if artifact_type and artifact_type not in SUPPORTED_ARTIFACT_TYPES:
            raise ValueError(f"Unsupported artifact type: {artifact_type}")
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if not 0 <= offset <= 100000:
            raise ValueError("offset must be between 0 and 100000")
        needle = (query or "").strip().casefold()
        records = self.manager.get_all_artifacts()
        selected = []
        for record in records:
            if not include_archived and record.get("archived", False):
                continue
            if artifact_type and record.get("type") != artifact_type:
                continue
            if needle:
                # Search only user-facing metadata; never use the internal file path
                # as a search term or accidentally expose it through search behavior.
                searchable_fields = (
                    "artifact_id", "type", "source", "timestamp", "created_at",
                    "created", "title", "name", "description", "filename",
                )
                searchable_text = " ".join(
                    str(record.get(field, "")) for field in searchable_fields
                ).casefold()
                if needle not in searchable_text:
                    continue
            selected.append(record)
        selected.sort(key=lambda record: (str(record.get("timestamp", record.get("created_at", record.get("created", "")))), str(record.get("artifact_id", ""))), reverse=True)
        total = len(selected)
        page = selected[offset:offset + limit]
        return {"artifacts": [{key: value for key, value in record.items() if key != "file"} for record in page], "pagination": {"total": total, "limit": limit, "offset": offset, "has_more": offset + len(page) < total}}
