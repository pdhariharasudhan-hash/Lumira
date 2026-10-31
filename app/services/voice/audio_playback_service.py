from app.services.artifacts.artifact_manager_service import ArtifactManagerService


class AudioPlaybackService:
    """Validate and resolve captured audio without accepting arbitrary paths."""

    def __init__(self, artifacts=None):
        self.artifacts = artifacts or ArtifactManagerService()

    def resolve(self, artifact_id: str) -> dict:
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            return {"success": False, "code": "invalid_audio_artifact"}
        artifact_id = artifact_id.strip()
        artifact = self.artifacts.get_artifact(artifact_id)
        if not artifact:
            return {"success": False, "code": "audio_not_found"}
        if artifact.get("type") != "audio":
            return {"success": False, "code": "artifact_is_not_audio"}
        path = self.artifacts.get_artifact_path(artifact_id)
        if path is None or not path.is_file():
            return {"success": False, "code": "audio_unavailable"}
        return {"success": True, "artifact_id": artifact_id, "audio_artifact": artifact}
