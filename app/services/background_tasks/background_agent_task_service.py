from __future__ import annotations
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from app.services.sessions.session_manager_service import redact_sensitive_value, redact_sensitive_text
from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError

class BackgroundAgentTaskService:
    """Durable, explicitly submitted agent jobs; never schedules recurring work."""
    MAX_TASKS = 500
    MAX_TASK_LENGTH = 10_000
    MAX_RESULT_CHARS = 20_000
    MAX_RETRIES = 3
    STATUSES = {"queued", "running", "completed", "failed", "interrupted", "cancelled"}
    AGENTS = {"planner_agent", "research_agent", "code_agent"}

    def __init__(self, storage_path: str | Path = "memory/background_agent_tasks.json", executor=None, autonomy_service=None):
        self.storage_path = Path(storage_path)
        self.executor = executor
        self.autonomy_service = autonomy_service
        self._lock = threading.RLock()
        self.store = AtomicJsonStore(self.storage_path)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _validate_items(self, data):
        if not isinstance(data, list) or len(data) > self.MAX_TASKS or any(not isinstance(item, dict) for item in data):
            raise PersistenceIntegrityError("Background task storage has an invalid shape.")
        seen = set()
        idempotency_keys = set()
        for item in data:
            task_id = item.get("task_id")
            if not isinstance(task_id, str) or not task_id or task_id in seen:
                raise PersistenceIntegrityError("Background task storage contains an invalid task identity.")
            seen.add(task_id)
            idempotency_key = item.get("idempotency_key")
            if idempotency_key is not None:
                if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 128 or idempotency_key in idempotency_keys:
                    raise PersistenceIntegrityError("Background task idempotency key is invalid or duplicated.")
                idempotency_keys.add(idempotency_key)
            if (
                not isinstance(item.get("task"), str)
                or not item["task"].strip()
                or len(item["task"]) > BackgroundAgentTaskService.MAX_TASK_LENGTH
                or not isinstance(item.get("status"), str)
                or item["status"] not in BackgroundAgentTaskService.STATUSES
                or (
                    item.get("agent_name") is not None
                    and (
                        not isinstance(item.get("agent_name"), str)
                        or item["agent_name"] not in BackgroundAgentTaskService.AGENTS
                    )
                )
                or not isinstance(item.get("autonomous", False), bool)
            ):
                raise PersistenceIntegrityError("Background task storage contains an invalid task record.")
            retry_count = item.get("retry_count", 0)
            if not isinstance(retry_count, int) or isinstance(retry_count, bool) or not 0 <= retry_count <= BackgroundAgentTaskService.MAX_RETRIES:
                raise PersistenceIntegrityError("Background task retry count is invalid.")
            for field, maximum in (("result", BackgroundAgentTaskService.MAX_RESULT_CHARS), ("error", 1000)):
                value = item.get(field)
                if value is not None and (not isinstance(value, str) or len(value) > maximum):
                    raise PersistenceIntegrityError(f"Background task {field} is invalid.")
        return data

    def _load(self):
        return self._validate_items(self.store.read(default=[]))

    def _update(self, mutator, *, write_if_changed: bool = False):
        def apply(items):
            self._validate_items(items)
            result = mutator(items)
            self._validate_items(items)
            return result
        return self.store.update(apply, default=[], write_if_changed=write_if_changed)

    def recover_interrupted(self):
        """Mark abandoned running jobs at application startup; preserve queued work."""
        with self._lock:
            def recover(items):
                changed = 0
                for item in items:
                    if item.get("status") == "running":
                        item["status"] = "interrupted"
                        item["updated_at"] = self._now()
                        item["error"] = "The application restarted before this background job finished. Review and submit it again."
                        changed += 1
                return changed
            return self._update(recover, write_if_changed=True)

    def create(
        self,
        task: str,
        agent_name: str | None = None,
        autonomous: bool = False,
        *,
        idempotency_key: str | None = None,
    ):
        if idempotency_key is not None and (
            not isinstance(idempotency_key, str)
            or not idempotency_key.strip()
            or len(idempotency_key) > 128
        ):
            return {"success": False, "code": "invalid_idempotency_key"}
        if not isinstance(task, str) or not task.strip() or len(task) > self.MAX_TASK_LENGTH:
            return {"success": False, "code": "invalid_task", "message": f"Task must contain 1 to {self.MAX_TASK_LENGTH} characters."}
        if agent_name is not None and (
            not isinstance(agent_name, str)
            or agent_name not in self.AGENTS
        ):
            return {"success": False, "code": "invalid_agent", "message": "Select a registered agent or automatic routing."}
        if not isinstance(autonomous, bool):
            return {"success": False, "code": "invalid_autonomous_flag", "message": "autonomous must be a boolean."}
        authorization = {"allowed": True, "mode": "interactive"}
        if autonomous:
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
        safe_task = redact_sensitive_text(task.strip())
        if not safe_task:
            return {"success": False, "code": "invalid_task_after_redaction"}
        with self._lock:
            item = {"task_id": str(uuid4()), "task": safe_task, "agent_name": agent_name,
                    "autonomous": autonomous, "status": "queued",
                    "created_at": self._now(), "updated_at": self._now()}
            if idempotency_key is not None:
                item["idempotency_key"] = idempotency_key.strip()
            def insert(items):
                if idempotency_key is not None:
                    existing = next((entry for entry in items if entry.get("idempotency_key") == idempotency_key.strip()), None)
                    if existing is not None:
                        return {"duplicate": True, "task": dict(existing)}
                if len(items) >= self.MAX_TASKS:
                    terminal = next((index for index, entry in enumerate(items) if entry.get("status") in {"completed", "failed", "interrupted", "cancelled"}), None)
                    if terminal is None:
                        return {"error": "task_capacity_reached"}
                    items.pop(terminal)
                items.append(item)
                return {"duplicate": False, "task": dict(item)}
            created = self._update(insert)
        if isinstance(created, dict) and created.get("error"):
            return {"success": False, "code": created["error"]}
        return {"success": True, "duplicate": created.get("duplicate", False), "task": created.get("task", created)}

    def retry(self, task_id: str, *, owner_confirmed: bool) -> dict:
        if owner_confirmed is not True:
            return {"success": False, "code": "explicit_owner_confirmation_required"}
        if not isinstance(task_id, str) or not task_id.strip():
            return {"success": False, "code": "invalid_task_id"}

        def requeue(items):
            item = next((entry for entry in items if entry.get("task_id") == task_id), None)
            if item is None:
                return {"error": "task_not_found"}
            if item.get("status") not in {"failed", "interrupted"}:
                return {"error": "task_not_retryable"}
            if item.get("retry_count", 0) >= self.MAX_RETRIES:
                return {"error": "retry_limit_reached"}
            if item.get("autonomous") is True:
                try:
                    service = self.autonomy_service
                    if service is None:
                        from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
                        service = AutonomyPermissionService()
                    authorization = service.authorize("agent.dispatch", autonomous=True)
                except Exception:
                    return {"error": "autonomous_permission_state_unavailable"}
                if not isinstance(authorization, dict) or authorization.get("allowed") is not True:
                    return {"error": authorization.get("code", "autonomous_permission_required") if isinstance(authorization, dict) else "autonomous_permission_required"}
            item["status"] = "queued"
            item["updated_at"] = self._now()
            item["error"] = None
            item["result"] = None
            item["retry_count"] = item.get("retry_count", 0) + 1
            return dict(item)

        try:
            result = self._update(requeue)
        except Exception:
            return {"success": False, "code": "task_storage_unavailable"}
        return {"success": "error" not in result, "task": result if "error" not in result else None, "code": result.get("error")}

    def cancel(self, task_id: str, *, owner_confirmed: bool) -> dict:
        if owner_confirmed is not True:
            return {"success": False, "code": "explicit_owner_confirmation_required"}
        if not isinstance(task_id, str) or not task_id.strip():
            return {"success": False, "code": "invalid_task_id"}

        def cancel_task(items):
            item = next((entry for entry in items if entry.get("task_id") == task_id), None)
            if item is None:
                return {"error": "task_not_found"}
            if item.get("status") != "queued":
                return {"error": "task_not_cancellable"}
            item["status"] = "cancelled"
            item["updated_at"] = self._now()
            item["error"] = None
            return dict(item)

        try:
            result = self._update(cancel_task)
        except Exception:
            return {"success": False, "code": "task_storage_unavailable"}
        return {"success": "error" not in result, "task": result if "error" not in result else None, "code": result.get("error")}

    def list(self, status: str | None = None, limit: int = 100):
        if status is not None and (not isinstance(status, str) or status not in self.STATUSES):
            return {"success": False, "code": "invalid_status", "tasks": [], "count": 0}
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            return {"success": False, "code": "invalid_limit", "tasks": [], "count": 0}
        with self._lock:
            items = self._load()
            filtered = [item for item in items if status is None or item.get("status") == status]
            return {"success": True, "tasks": filtered[-limit:], "count": len(filtered)}

    def get(self, task_id: str):
        if not isinstance(task_id, str) or not task_id.strip():
            return None
        with self._lock:
            return next((item for item in self._load() if item.get("task_id") == task_id), None)

    def execute(self, task_id: str):
        with self._lock:
            def claim(items):
                item = next((entry for entry in items if entry.get("task_id") == task_id), None)
                if item is None:
                    return {"error": "task_not_found"}
                if item.get("status") != "queued":
                    return {"error": "task_not_queued"}
                item["status"] = "running"
                item["updated_at"] = self._now()
                return {"task": item["task"], "agent_name": item.get("agent_name"),
                        "autonomous": item.get("autonomous", False)}
            claimed = self._update(claim)
            if "error" in claimed:
                return {"success": False, "code": claimed["error"]}
            task, agent_name, autonomous = claimed["task"], claimed["agent_name"], claimed["autonomous"]

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
            error = None if succeeded else redact_sensitive_text(
                str(outcome.get("message", outcome.get("code", "Agent task failed.")))[:1000]
            )
        except Exception as exc:
            status, result = "failed", None
            error = f"Background execution failed ({type(exc).__name__})."

        with self._lock:
            def finish(items):
                item = next((entry for entry in items if entry.get("task_id") == task_id), None)
                if item is None:
                    return None
                item.update({"status": status, "updated_at": self._now(), "result": result, "error": error})
                return dict(item)
            completed = self._update(finish)
            if completed is None:
                return {"success": False, "code": "task_not_found"}

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
                completed["autonomy_event_error"] = "Autonomous lifecycle state could not be persisted."
                with self._lock:
                    self._update(lambda items: next(
                        (item.update({"autonomy_event_error": completed["autonomy_event_error"]})
                         for item in items if item.get("task_id") == task_id), None
                    ))
        return {"success": status == "completed", "task": completed}
