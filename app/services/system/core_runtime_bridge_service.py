from app.services.system.personal_ai_status_service import PersonalAIStatusService
from app.services.system.core_feature_bridge_service import CoreFeatureBridgeService
from app.services.resources.resource_budget_service import ResourceBudgetService
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.voice.wake_word_listener_service import WakeWordListenerService
from app.services.sessions.session_manager_service import SessionManagerService


class CoreRuntimeBridgeService:
    """Main-core runtime bridge for subsystems that otherwise operate independently."""

    def __init__(self, status=None, features=None, resources=None, artifacts=None, wake_word=None, sessions=None):
        self.status = status or PersonalAIStatusService()
        self.features = features or CoreFeatureBridgeService()
        self.resources = resources or ResourceBudgetService()
        self.artifacts = artifacts or ArtifactManagerService()
        self.wake_word = wake_word or WakeWordListenerService()
        self.sessions = sessions or SessionManagerService()

    @staticmethod
    def _safe(name, callback):
        try:
            return {"available": True, "data": callback()}
        except Exception as exc:
            return {"available": False, "error": type(exc).__name__, "subsystem": name}

    def overview(self):
        return {
            "success": True,
            "core": self._safe("core", self.status.overview),
            "features": self._safe("features", self.features.overview),
            "resources": self._safe("resources", self.resources.snapshot),
            "artifacts": self._safe("artifacts", self.artifacts.stats),
            "voice": self._safe("voice", self.wake_word.status),
        }

    def context(self, session_id: str | None = None, project_id: str | None = None, goal_id: str | None = None):
        context = {
            "session_id": session_id,
            "project_id": project_id,
            "goal_id": goal_id,
            "core_status": self._safe("core", self.status.snapshot),
            "resource_status": self._safe("resources", self.resources.snapshot),
        }
        if session_id:
            context["session"] = self._safe("session", lambda: self.sessions.get_session(session_id))
        return {"success": True, "context": context}
