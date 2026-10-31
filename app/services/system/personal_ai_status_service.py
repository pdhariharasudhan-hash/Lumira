from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.features.feature_registry_service import FeatureRegistryService
from app.services.notepad_service import NotepadService
from app.services.research.research_library_service import ResearchLibraryService
from app.services.recovery.recovery_checkpoint_service import RecoveryCheckpointService

class PersonalAIStatusService:
    """Bounded, read-only overview of Lumira's local personal knowledge systems."""

    def snapshot(self):
        artifacts = ArtifactManagerService().availability_summary()
        features = FeatureRegistryService().list_features()
        notes = NotepadService().note_summary()
        research = ResearchLibraryService().summary()
        checkpoints = RecoveryCheckpointService().list_recent(100)
        return {
            "knowledge": {
                "notes": notes,
                "research": research,
                "artifacts": artifacts,
            },
            "features": {
                "total": features.get("count", 0),
                "enabled": len(features.get("enabled", [])),
                "available": len(features.get("available", [])),
                "failed": len(features.get("failed", [])),
            },
            "recovery": {
                "checkpoint_count": len(checkpoints),
                "latest": checkpoints[0] if checkpoints else None,
            },
        }
