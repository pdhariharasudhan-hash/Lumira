from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


AUTONOMY_SCHEMA_VERSION = 1
AUTONOMY_OPERATIONS = {"agent.dispatch", "workflow.run", "code.execute"}
MAX_EVENTS = 200


class AutonomyPermissionService:
    """Fail-closed durable permissions and lifecycle state for autonomous work."""

    def __init__(self, path: str | Path = "memory/autonomy_permissions.json"):
        self.store = AtomicJsonStore(path)
        if not Path(path).exists():
            self.store.write({
                "schema_version": AUTONOMY_SCHEMA_VERSION,
                "permissions": {},
                "events": [],
            })

    @staticmethod
    def _operation(operation: str) -> str:
        if not isinstance(operation, str) or operation not in AUTONOMY_OPERATIONS:
            raise ValueError("unsupported autonomous operation")
        return operation

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _read(self) -> dict:
        document = self.store.read()
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != AUTONOMY_SCHEMA_VERSION
            or not isinstance(document.get("permissions"), dict)
            or not isinstance(document.get("events"), list)
            or len(document["events"]) > MAX_EVENTS
        ):
            raise PersistenceIntegrityError("Autonomy permission store is invalid")
        return document

    def status(self) -> dict:
        document = self._read()
        permissions = {}
        for operation in sorted(AUTONOMY_OPERATIONS):
            record = document["permissions"].get(operation, {})
            permissions[operation] = {
                "enabled": record.get("enabled") is True,
                "updated_at": record.get("updated_at"),
                "reason": record.get("reason"),
            }
        return {"success": True, "permissions": permissions, "recent_events": document["events"][-20:]}

    def set_permission(self, operation: str, enabled: bool, reason: str | None = None) -> dict:
        operation = self._operation(operation)
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        if reason is not None and (not isinstance(reason, str) or len(reason) > 500):
            raise ValueError("reason must be at most 500 characters")
        timestamp = self._now()

        def mutate(document):
            document["permissions"][operation] = {
                "enabled": enabled,
                "updated_at": timestamp,
                "reason": reason.strip() if isinstance(reason, str) else None,
            }
            self._append_event(document, operation, "permission_granted" if enabled else "permission_revoked")
            return document["permissions"][operation]

        record = self.store.update(mutate, default={
            "schema_version": AUTONOMY_SCHEMA_VERSION, "permissions": {}, "events": [],
        })
        return {"success": True, "operation": operation, "permission": record}

    def authorize(self, operation: str, *, autonomous: bool) -> dict:
        operation = self._operation(operation)
        if autonomous is not True:
            return {"allowed": True, "operation": operation, "mode": "interactive"}
        document = self._read()
        record = document["permissions"].get(operation)
        if not isinstance(record, dict) or record.get("enabled") is not True:
            return {
                "allowed": False,
                "operation": operation,
                "mode": "autonomous",
                "code": "autonomous_permission_required",
                "message": f"Explicit permission is required for autonomous operation '{operation}'.",
            }
        return {
            "allowed": True,
            "operation": operation,
            "mode": "autonomous",
            "permission_updated_at": record.get("updated_at"),
        }

    def record_state(self, operation: str, state: str, *, run_id: str | None = None, detail: str | None = None) -> dict:
        operation = self._operation(operation)
        if not isinstance(state, str) or not state.strip() or len(state) > 40:
            raise ValueError("state must contain 1-40 characters")
        event = {
            "event_id": uuid4().hex,
            "operation": operation,
            "state": state.strip(),
            "run_id": run_id if isinstance(run_id, str) and len(run_id) <= 128 else None,
            "detail": detail[:500] if isinstance(detail, str) else None,
            "timestamp": self._now(),
        }

        def mutate(document):
            self._append_event(document, operation, event["state"], event)
            return event

        return self.store.update(mutate, default={
            "schema_version": AUTONOMY_SCHEMA_VERSION, "permissions": {}, "events": [],
        })

    @staticmethod
    def _append_event(document: dict, operation: str, state: str, event: dict | None = None) -> None:
        item = event or {
            "event_id": uuid4().hex,
            "operation": operation,
            "state": state,
            "run_id": None,
            "detail": None,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        document["events"].append(item)
        del document["events"][:-MAX_EVENTS]
