from __future__ import annotations

from app.services.artifacts.artifact_manager_service import ArtifactManagerService


class VoiceHistoryService:
    """Read-only personal history of voice artifacts and their related records."""

    def __init__(self, artifacts: ArtifactManagerService | None = None):
        self.artifacts = artifacts or ArtifactManagerService()

    def list(self, limit: int = 100) -> list[dict]:
        if not 0 <= limit <= 200:
            raise ValueError("limit must be between 0 and 200")
        records = self.artifacts.get_all_artifacts()
        voice_types = {
            "audio", "transcript", "transcripts", "summary", "summaries", "voice_idea"
        }
        items = [dict(x) for x in records if isinstance(x, dict) and (x.get("type") in voice_types or x.get("source") == "voice_capture")]
        return list(reversed(items[-limit:])) if limit else []
