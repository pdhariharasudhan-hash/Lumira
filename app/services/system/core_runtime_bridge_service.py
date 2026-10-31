from app.services.system.personal_ai_status_service import PersonalAIStatusService
from app.services.system.core_feature_bridge_service import CoreFeatureBridgeService
from app.services.resources.resource_budget_service import ResourceBudgetService
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.voice.wake_word_listener_service import WakeWordListenerService
from app.services.sessions.session_manager_service import SessionManagerService
from app.services.memory.memory_service import MemoryService
from app.services.recovery.recovery_checkpoint_service import RecoveryCheckpointService
from app.services.learning.learning_module import LearningModule
from app.services.lifecycle.project_lifecycle_service import ProjectLifecycleService
from app.services.devices.device_registry_service import DeviceRegistryService
from app.services.search.unified_search_service import UnifiedSearchService
from app.agents.agent_manager import AgentManager
from app.services.personal_context.personal_context_service import PersonalContextService


class CoreRuntimeBridgeService:
    """Main-core runtime bridge for subsystems that otherwise operate independently."""

    def __init__(self, status=None, features=None, resources=None, artifacts=None, wake_word=None, sessions=None, memory=None, recovery=None, learning=None, projects=None, devices=None, search=None, agents=None, personal_context=None):
        self.status = status or PersonalAIStatusService()
        self.features = features or CoreFeatureBridgeService()
        self.resources = resources or ResourceBudgetService()
        self.artifacts = artifacts or ArtifactManagerService()
        self.wake_word = wake_word or WakeWordListenerService()
        self.sessions = sessions or SessionManagerService()
        self.memory = memory or MemoryService()
        self.recovery = recovery or RecoveryCheckpointService()
        self.learning = learning or LearningModule()
        self.projects = projects or ProjectLifecycleService()
        self.devices = devices or DeviceRegistryService()
        self.search = search or UnifiedSearchService()
        self.agents = agents or AgentManager()
        self.personal_context = personal_context or PersonalContextService()

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
            "memory": self._safe("memory", self._memory_summary),
            "recovery": self._safe("recovery", self.recovery.summary),
            "learning": self._safe("learning", self._learning_summary),
            "projects": self._safe("projects", self._project_summary),
            "devices": self._safe("devices", self._device_summary),
            "agents": self._safe("agents", self._agent_summary),
            "personal_context": self._safe("personal_context", self._personal_context_summary),
        }

    def _memory_summary(self):
        data = self.memory.get_all()
        return {
            "goals": len(data.get("goals", [])),
            "decisions": len(data.get("decisions", [])),
            "experiences": len(data.get("experiences", [])),
            "learning_records": len(data.get("learning_records", [])),
        }

    def _agent_summary(self):
        names = self.agents.list_agents()
        return {"total": len(names), "agents": list(names)}

    def _personal_context_summary(self):
        snapshot = self.personal_context.snapshot("", 5)
        if not isinstance(snapshot, dict):
            return {"available": False}
        return {
            "available": True,
            "note_count": len(snapshot.get("notes", [])),
            "project_count": len(snapshot.get("projects", [])),
        }

    def _project_summary(self):
        projects = self.projects.list_projects()
        values = projects.get("projects", []) if isinstance(projects, dict) else []
        return {"total": len(values), "available": True}

    def _device_summary(self):
        devices = self.devices.list_devices(limit=200)
        counts = {}
        for device in devices:
            state = device.get("status", "unknown")
            counts[state] = counts.get(state, 0) + 1
        return {"total": len(devices), "statuses": counts}

    def search_context(self, query: str, limit: int = 20):
        if not isinstance(query, str) or not query.strip():
            return {"success": False, "error": "invalid_query"}
        result = self.search.search_all(query.strip())
        items = result.get("items", []) if isinstance(result, dict) else []
        return {"success": True, "query": query.strip(), "count": min(len(items), limit), "items": items[:limit]}

    def _learning_summary(self):
        return {"available": self.learning is not None, "engine": "learning"}

    def checkpoint_context(self, workflow_id: str | None = None):
        if not workflow_id:
            return {"success": True, "checkpoint": None}
        return {"success": True, "checkpoint": self.recovery.resume(workflow_id)}

    def execution_context(self, operation: str, session_id: str | None = None, project_id: str | None = None, goal_id: str | None = None):
        if not isinstance(operation, str) or not operation.strip():
            return {"success": False, "error": "invalid_operation"}
        context = self.context(session_id, project_id, goal_id).get("context", {})
        return {
            "success": True,
            "operation": operation.strip(),
            "context": context,
            "bridge_health": self.features.bridge_health(),
        }

    def agent_context(self, task: str, session_id: str | None = None, project_id: str | None = None, goal_id: str | None = None):
        if not isinstance(task, str) or not task.strip():
            return {"success": False, "error": "invalid_task"}
        context = self.context(session_id, project_id, goal_id).get("context", {})
        return {
            "success": True,
            "task": task.strip(),
            "core_context": context,
            "available_agents": self._safe("agents", self._agent_summary),
        }

    def context(self, session_id: str | None = None, project_id: str | None = None, goal_id: str | None = None):
        context = {
            "session_id": session_id,
            "project_id": project_id,
            "goal_id": goal_id,
            "core_status": self._safe("core", self.status.snapshot),
            "resource_status": self._safe("resources", self.resources.snapshot),
            "memory_status": self._safe("memory", self._memory_summary),
        }
        if session_id:
            context["session"] = self._safe("session", lambda: self.sessions.get_session(session_id))
        return {"success": True, "context": context}
