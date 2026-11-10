from __future__ import annotations
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from app.services.sessions.session_manager_service import redact_sensitive_value, redact_sensitive_text
from app.services.persistence.atomic_json_store import PersistenceIntegrityError

class BackgroundAgentTaskService:
    """Durable, explicitly submitted agent jobs; never schedules recurring work."""
    MAX_TASKS = 500
    MAX_TASK_LENGTH = 10_000
    MAX_RESULT_CHARS = 20_000

    def __init__(self, storage_path: str | Path = "memory/background_agent_tasks.json", executor=None, autonomy_service=None):
        self.storage_path = Path(storage_path)
        self.executor = executor
        self.autonomy_service = autonomy_service
        self._lock = threading.RLock()
        self._recover_interrupted()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _load(self):
        if not self.storage_path.exists():
            return []
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Background task storage is unavailable or invalid.") from exc
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise RuntimeError("Background task storage has an invalid shape.")
        return data

    def _save(self, items):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.storage_path.with_name(f".{self.storage_path.name}.{uuid4().hex}.tmp")
        try:
            temp.write_text(json.dumps(items[-self.MAX_TASKS:], ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, self.storage_path)
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    def _recover_interrupted(self):
        with self._lock:
            items = self._load()
            changed = False
            for item in items:
                if item.get("status") in {"queued", "running"}:
                    item["status"] = "interrupted"
                    item["updated_at"] = self._now()
                    item["error"] = "The application restarted before this background job finished. Review and submit it again."
                    changed = True
            if changed:
                self._save(items)

    def create(self, task: str, agent_name: str | None = None, autonomous: bool = False):
        if not isinstance(task, str) or not task.strip() or len(task) > self.MAX_TASK_LENGTH:
            return {"success": False, "code": "invalid_task", "message": f"Task must contain 1 to {self.MAX_TASK_LENGTH} characters."}
        if agent_name not in {None, "planner_agent", "research_agent", "code_agent"}:
            return {"success": False, "code": "invalid_agent", "message": "Select a registered agent or automatic routing."}
        if not isinstance(autonomous, bool):
            return {"success": False, "code": "invalid_autonomous_flag", "message": "autonomous must be a boolean."}
        authorization = {"allowed": True, "mode": "interactive"}
        if autonomous:
            from app.services.persistence.atomic_json_store import PersistenceIntegrityError
            try:
                service = self.autonomy_service
                if service is None:
                    from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
                    service = AutonomyPermissionService()
                authorization = service.authorize("agent.dispatch", autonomous=True)
            except PersistenceIntegrityError:
                return {"success": False, "code": "autonomous_permission_state_unavailable",
                        "message": "Autonomous background execution is blocked because permission state is unavailable."}
            if not authorization["allowed"]:
                return {"success": False, "code": authorization["code"], "message": authorization["message"],
                        "authorization": authorization}
        with self._lock:
            items = self._load()
            if len(items) >= self.MAX_TASKS:
                items = items[-(self.MAX_TASKS - 1):]
            item = {"task_id": str(uuid4()), "task": task.strip(), "agent_name": agent_name,
                    "autonomous": autonomous,
                    "status": "queued", "created_at": self._now(), "updated_at": self._now()}
            items.append(item)
            self._save(items)
        return {"success": True, "task": item}

    def list(self, status: str | None = None, limit: int = 100):
        with self._lock:
            items = self._load()
            filtered = [item for item in items if status is None or item.get("status") == status]
            return {"success": True, "tasks": filtered[-max(1, min(limit, 200)):], "count": len(filtered)}

    def get(self, task_id: str):
        with self._lock:
            return next((item for item in self._load() if item.get("task_id") == task_id), None)

    def execute(self, task_id: str):
        with self._lock:
            items = self._load()
            item = next((entry for entry in items if entry.get("task_id") == task_id), None)
            if item is None:
                return {"success": False, "code": "task_not_found"}
            if item.get("status") != "queued":
                return {"success": False, "code": "task_not_queued"}
            item["status"] = "running"
            item["updated_at"] = self._now()
            self._save(items)
            task, agent_name, autonomous = item["task"], item.get("agent_name"), item.get("autonomous", False)
        try:
            executor = self.executor
            if executor is None:
                from app.services.brain.brain_agent_orchestrator import BrainAgentOrchestrator
                executor = BrainAgentOrchestrator()
            if autonomous:
                outcome = executor.execute(task, agent_name=agent_name, autonomous=True)
            else:
                outcome = executor.execute(task, agent_name=agent_name)
            succeeded = isinstance(outcome, dict) and outcome.get("success") is True
            safe_outcome = redact_sensitive_value(outcome)
            result = json.dumps(safe_outcome, ensure_ascii=False, default=str)[:self.MAX_RESULT_CHARS]
            status = "completed" if succeeded else "failed"
            error = None if succeeded else redact_sensitive_text(str(outcome.get("message", outcome.get("code", "Agent task failed.")))[:1000])
        except Exception as exc:
            status, result = "failed", None
            error = f"Background execution failed ({type(exc).__name__})."
        with self._lock:
            items = self._load()
            item = next((entry for entry in items if entry.get("task_id") == task_id), None)
            if item is None:
                return {"success": False, "code": "task_not_found"}
            item.update({"status": status, "updated_at": self._now(), "result": result, "error": error})
            if autonomous:
                try:
                    service = self.autonomy_service
                    if service is None:
                        from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
                        service = AutonomyPermissionService()
                    service.record_state(
                        "agent.dispatch", status, run_id=task_id,
                        detail=error or "background agent task finished",
                    )
                except (OSError, ValueError, PersistenceIntegrityError):
                    item["autonomy_event_error"] = "Autonomous lifecycle state could not be persisted."
            self._save(items)
            return {"success": status == "completed", "task": item}
