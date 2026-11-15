from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


class SystemHealthService:
    """Run bounded read-only health probes against core personal-AI subsystems."""

    def __init__(self, event_service=None, notification_service=None, memory_service=None):
        self.event_service = event_service
        self.notification_service = notification_service
        self.memory_service = memory_service

    @staticmethod
    def _check(name: str, probe) -> dict[str, Any]:
        try:
            details = probe()
            if details is False:
                return {"status": "degraded", "error": "probe_failed"}
            if isinstance(details, dict) and details.get("success") is False:
                return {"status": "degraded", **details}
            return {"status": "healthy", **(details if isinstance(details, dict) else {})}
        except Exception as exc:
            return {"status": "degraded", "error": type(exc).__name__}

    def snapshot(self) -> dict[str, Any]:
        checks: dict[str, dict[str, Any]] = {}

        def events_probe():
            events = self.event_service
            if events is None:
                from app.services.system.core_event_log_service import CoreEventLogService
                events = CoreEventLogService()
            result = events.recent(1)
            return {"recent_event_count": len(result.get("events", []))}

        def notification_probe():
            notifications = self.notification_service
            if notifications is None:
                from app.services.notifications.notification_service import NotificationService
                notifications = NotificationService()
            result = notifications.list(unread_only=True)
            return {"unread_count": len(result.get("notifications", []))}

        def memory_probe():
            memory = self.memory_service
            if memory is None:
                from app.services.memory.memory_service import MemoryService
                memory = MemoryService()
            data = memory._read_cognitive_memory()
            return {
                "decisions": len(data.get("decisions", [])),
                "experiences": len(data.get("experiences", [])),
                "learning_records": len(data.get("learning_records", [])),
            }

        def workflow_probe():
            from app.services.work_items.work_item_service import WorkItemService
            workflows = WorkItemService().list_workflows(limit=1)
            return {"sampled_workflows": len(workflows)}

        def artifact_probe():
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService
            records = ArtifactManagerService().get_all_artifacts()
            return {"artifact_count": len(records)}

        def storage_probe():
            paths = [Path("memory"), Path("data")]
            return {"storage_roots": {
                str(path): {"present": path.exists(), "is_directory": path.is_dir()}
                for path in paths
            }}

        def dependency_probe():
            requirements = Path("requirements.txt")
            if not requirements.is_file():
                raise FileNotFoundError("requirements.txt")
            checked = []
            missing = []
            mismatched = []
            for raw in requirements.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                package = line.split("==", 1)[0].strip()
                expected = line.split("==", 1)[1].strip() if "==" in line else None
                try:
                    installed = version(package)
                except PackageNotFoundError:
                    missing.append(package)
                    continue
                checked.append(package)
                if expected and installed != expected:
                    mismatched.append({"package": package, "expected": expected, "installed": installed})
            return {
                "checked_count": len(checked),
                "missing": missing,
                "version_mismatches": mismatched,
                "success": not missing and not mismatched,
            }

        def event_bus_probe():
            from app.services.system.event_bus_service import EventBusService
            result = EventBusService().list_events(limit=1)
            if result.get("success") is not True:
                return {"success": False, "code": result.get("code", "event_bus_unavailable")}
            return {"stored_event_count_sample": len(result.get("events", []))}

        def queue_probe():
            from app.services.system.message_queue_service import MessageQueueService
            result = MessageQueueService().list(limit=1)
            if result.get("success") is not True:
                return {"success": False, "code": result.get("code", "queue_unavailable")}
            return {"stored_message_count_sample": len(result.get("messages", []))}

        def scheduler_probe():
            from app.services.system.task_scheduler_service import TaskSchedulerService
            result = TaskSchedulerService().list(limit=1)
            if result.get("success") is not True:
                return {"success": False, "code": result.get("code", "scheduler_unavailable")}
            return {"stored_job_count_sample": len(result.get("jobs", []))}

        def project_preview_probe():
            from app.services.workspace.project_preview_service import ProjectPreviewService
            service = ProjectPreviewService()
            records = service._require_records(service.store.read([]))
            return {
                "registered_previews": sum(1 for item in records if item.get("status") == "registered"),
                "stopped_previews": sum(1 for item in records if item.get("status") == "stopped"),
                "indexed_previews": len(records),
            }

        def background_task_probe():
            from app.services.background_tasks.background_agent_task_service import BackgroundAgentTaskService
            result = BackgroundAgentTaskService().list(limit=1)
            if result.get("success") is not True:
                return {"success": False, "code": result.get("code", "background_tasks_unavailable")}
            return {"stored_task_count_sample": len(result.get("tasks", []))}

        def agent_lease_probe():
            from app.services.system.agent_execution_lease_service import AgentExecutionLeaseService
            result = AgentExecutionLeaseService().snapshot()
            if result.get("success") is not True:
                return {"success": False, "code": result.get("code", "agent_lease_store_unavailable")}
            return {
                "active_leases": result.get("active_count", 0),
                "max_concurrent_agents": result.get("max_concurrent_agents", 1),
                "resource_pressure": result.get("resource_pressure", "unknown"),
            }

        def resource_probe():
            from app.services.resources.resource_budget_service import ResourceBudgetService
            result = ResourceBudgetService().snapshot()
            memory = result.get("memory", {})
            return {
                "resource_pressure": result.get("resource_pressure", "unknown"),
                "available_gib": memory.get("available_gib"),
                "profile": result.get("policy", {}).get("profile", "unknown"),
                "max_concurrent_agents": result.get("policy", {}).get("max_concurrent_agents", 1),
            }

        def model_health_probe():
            from app.services.multi_model.model_health_service import ModelHealthService
            result = ModelHealthService().snapshot()
            if result.get("success") is not True:
                return {"success": False, "code": result.get("code", "model_health_unavailable")}
            records = result.get("models", {})
            return {
                "tracked_models": result.get("count", 0),
                "open_circuits": sum(1 for item in records.values() if isinstance(item, dict) and item.get("circuit_open") is True),
            }

        checks["core_events"] = self._check("core_events", events_probe)
        checks["event_bus"] = self._check("event_bus", event_bus_probe)
        checks["message_queue"] = self._check("message_queue", queue_probe)
        checks["task_scheduler"] = self._check("task_scheduler", scheduler_probe)
        checks["project_previews"] = self._check("project_previews", project_preview_probe)
        checks["background_tasks"] = self._check("background_tasks", background_task_probe)
        checks["agent_execution_leases"] = self._check("agent_execution_leases", agent_lease_probe)
        checks["resource_budget"] = self._check("resource_budget", resource_probe)
        checks["model_health"] = self._check("model_health", model_health_probe)
        checks["notifications"] = self._check("notifications", notification_probe)
        checks["cognitive_memory"] = self._check("cognitive_memory", memory_probe)
        checks["workflows"] = self._check("workflows", workflow_probe)
        checks["artifacts"] = self._check("artifacts", artifact_probe)
        checks["storage"] = self._check("storage", storage_probe)
        checks["dependencies"] = self._check("dependencies", dependency_probe)

        degraded = [name for name, value in checks.items() if value["status"] != "healthy"]
        overall = "healthy" if not degraded else "degraded"
        return {
            "success": True,
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "degraded_subsystems": degraded,
        }
