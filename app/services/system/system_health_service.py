from __future__ import annotations

from datetime import datetime, timezone
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
            if details is False or (isinstance(details, dict) and details.get("success") is False):
                return {"status": "degraded", "error": "probe_failed"}
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
            return {"storage_roots": {str(path): {"exists": path.exists(), "writable": path.exists() and path.is_dir()} for path in paths}}

        checks["core_events"] = self._check("core_events", events_probe)
        checks["notifications"] = self._check("notifications", notification_probe)
        checks["cognitive_memory"] = self._check("cognitive_memory", memory_probe)
        checks["workflows"] = self._check("workflows", workflow_probe)
        checks["artifacts"] = self._check("artifacts", artifact_probe)
        checks["storage"] = self._check("storage", storage_probe)

        degraded = [name for name, value in checks.items() if value["status"] != "healthy"]
        overall = "healthy" if not degraded else "degraded"
        return {
            "success": True,
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "degraded_subsystems": degraded,
        }
