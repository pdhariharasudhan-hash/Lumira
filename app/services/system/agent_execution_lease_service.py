"""Cross-process RAM-aware agent execution leases backed by atomic JSON storage."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.resources.resource_budget_service import ResourceBudgetService


class AgentExecutionLeaseService:
    MAX_LEASES = 4
    LEASE_SECONDS = 4 * 60 * 60

    def __init__(self, storage_path: str = "memory/agent_execution_leases.json", budget=None):
        self.store = AtomicJsonStore(storage_path)
        self.budget = budget or ResourceBudgetService()
        self.store.read_or_create({"schema_version": 1, "leases": []})

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _validate(cls, document: Any) -> list[dict]:
        if not isinstance(document, dict) or document.get("schema_version") != 1:
            raise PersistenceIntegrityError("agent lease store schema is invalid")
        leases = document.get("leases")
        if not isinstance(leases, list) or len(leases) > cls.MAX_LEASES:
            raise PersistenceIntegrityError("agent lease list is invalid")
        ids, tasks = set(), set()
        for item in leases:
            if not isinstance(item, dict):
                raise PersistenceIntegrityError("agent lease record is invalid")
            lease_id, task_id, expires_at = item.get("lease_id"), item.get("task_id"), item.get("expires_at")
            if (
                not isinstance(lease_id, str) or not lease_id or lease_id in ids
                or not isinstance(task_id, str) or not task_id or task_id in tasks
                or not isinstance(expires_at, str)
            ):
                raise PersistenceIntegrityError("agent lease identity or expiry is invalid")
            ids.add(lease_id)
            tasks.add(task_id)
            try:
                expiry = datetime.fromisoformat(expires_at)
                if expiry.tzinfo is None:
                    raise ValueError("timezone required")
            except ValueError as exc:
                raise PersistenceIntegrityError("agent lease expiry is invalid") from exc
        return leases

    def acquire(self, task_id: str) -> dict:
        if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 128:
            return {"success": False, "code": "invalid_task_id"}
        try:
            snapshot = self.budget.snapshot()
            policy = snapshot.get("policy", {}) if isinstance(snapshot, dict) else {}
            max_active = policy.get("max_concurrent_agents", 1)
            if isinstance(max_active, bool) or not isinstance(max_active, int) or not 1 <= max_active <= self.MAX_LEASES:
                max_active = 1
        except Exception:
            return {"success": False, "code": "resource_budget_unavailable", "retry_after_seconds": 60}
        now = self._now()
        lease = {
            "lease_id": f"agent-lease-{uuid4()}",
            "task_id": task_id.strip(),
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.LEASE_SECONDS)).isoformat(),
            "resource_profile": policy.get("profile", "unknown"),
            "resource_pressure": snapshot.get("resource_pressure", "unknown"),
        }

        def insert(document):
            leases = self._validate(document)
            leases[:] = [
                item for item in leases
                if datetime.fromisoformat(item["expires_at"]).astimezone(timezone.utc) > now
            ]
            if any(item["task_id"] == task_id.strip() for item in leases):
                return {"error": "task_execution_lease_already_active"}
            if len(leases) >= max_active:
                return {"error": "resource_pressure_deferred"}
            leases.append(lease)
            return dict(lease)

        try:
            result = self.store.update(insert, {"schema_version": 1, "leases": []})
        except Exception:
            return {"success": False, "code": "execution_lease_storage_unavailable", "retry_after_seconds": 60}
        if isinstance(result, dict) and result.get("error"):
            return {
                "success": False,
                "code": result["error"],
                "retry_after_seconds": 30,
                "resource_pressure": snapshot.get("resource_pressure", "unknown"),
            }
        return {"success": True, "lease": result}

    def release(self, lease_id: str) -> dict:
        if not isinstance(lease_id, str) or not lease_id.strip():
            return {"success": False, "code": "invalid_lease_id"}

        def remove(document):
            leases = self._validate(document)
            before = len(leases)
            leases[:] = [item for item in leases if item["lease_id"] != lease_id]
            return {"released": len(leases) != before, "active_leases": len(leases)}

        try:
            result = self.store.update(remove, {"schema_version": 1, "leases": []})
        except Exception:
            return {"success": False, "code": "execution_lease_storage_unavailable"}
        return {"success": True, **result}

    def snapshot(self) -> dict:
        try:
            document = self.store.read({"schema_version": 1, "leases": []})
            leases = self._validate(document)
            now = self._now()
            active = [item for item in leases if datetime.fromisoformat(item["expires_at"]).astimezone(timezone.utc) > now]
            budget = self.budget.snapshot()
            return {
                "success": True,
                "active_count": len(active),
                "leases": active,
                "resource_pressure": budget.get("resource_pressure", "unknown"),
                "max_concurrent_agents": budget.get("policy", {}).get("max_concurrent_agents", 1),
            }
        except Exception:
            return {"success": False, "code": "execution_lease_storage_unavailable", "active_count": 0, "leases": []}
