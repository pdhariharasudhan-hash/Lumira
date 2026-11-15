from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.security.security_audit_log_service import SecurityAuditLogService


AUTONOMY_SCHEMA_VERSION = 1
AUTONOMY_OPERATIONS = {"agent.dispatch", "workflow.run", "code.execute", "device.command"}
MAX_EVENTS = 200


class AutonomyPermissionService:
    """Fail-closed durable permissions and lifecycle state for autonomous work."""

    def __init__(
        self,
        path: str | Path = "memory/autonomy_permissions.json",
        *,
        audit_log=None,
    ):
        self.store = AtomicJsonStore(path)
        self.audit_log = audit_log or SecurityAuditLogService()
        try:
            self.store.read_or_create(self._empty_document())
        except (OSError, PersistenceIntegrityError) as exc:
            raise PersistenceIntegrityError("Autonomy permission state could not be initialized") from exc

    @staticmethod
    def _empty_document() -> dict:
        return {"schema_version": AUTONOMY_SCHEMA_VERSION, "permissions": {}, "events": []}

    @staticmethod
    def _operation(operation: str) -> str:
        if not isinstance(operation, str) or operation not in AUTONOMY_OPERATIONS:
            raise ValueError("unsupported autonomous operation")
        return operation

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @classmethod
    def _validate_document(cls, document: dict) -> None:
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != AUTONOMY_SCHEMA_VERSION
            or not isinstance(document.get("permissions"), dict)
            or not isinstance(document.get("events"), list)
            or len(document["events"]) > MAX_EVENTS
        ):
            raise PersistenceIntegrityError("Autonomy permission store is invalid")
        if set(document["permissions"]) - AUTONOMY_OPERATIONS:
            raise PersistenceIntegrityError("Autonomy permission store contains an unknown operation")
        for operation, record in document["permissions"].items():
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("enabled"), bool)
                or not isinstance(record.get("updated_at"), str)
                or len(record["updated_at"]) > 40
                or (
                    record.get("reason") is not None
                    and (not isinstance(record["reason"], str) or len(record["reason"]) > 500)
                )
            ):
                raise PersistenceIntegrityError(f"Autonomy permission record is invalid: {operation}")
        for event in document["events"]:
            if (
                not isinstance(event, dict)
                or event.get("operation") not in AUTONOMY_OPERATIONS
                or not isinstance(event.get("state"), str)
                or not event["state"]
                or len(event["state"]) > 40
                or not isinstance(event.get("event_id"), str)
                or not isinstance(event.get("timestamp"), str)
            ):
                raise PersistenceIntegrityError("Autonomy permission event is invalid")
            if event.get("run_id") is not None and (
                not isinstance(event["run_id"], str) or len(event["run_id"]) > 128
            ):
                raise PersistenceIntegrityError("Autonomy event run identifier is invalid")
            if event.get("detail") is not None and (
                not isinstance(event["detail"], str) or len(event["detail"]) > 500
            ):
                raise PersistenceIntegrityError("Autonomy event detail is invalid")

    def _read(self) -> dict:
        document = self.store.read(default=self._empty_document())
        self._validate_document(document)
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
        return {
            "success": True,
            "permissions": permissions,
            "recent_events": document["events"][-20:],
        }

    def set_permission(self, operation: str, enabled: bool, reason: str | None = None) -> dict:
        operation = self._operation(operation)
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        if reason is not None and (
            not isinstance(reason, str) or len(reason) > 500
        ):
            raise ValueError("reason must be at most 500 characters")
        timestamp = self._now()
        audit_details = {
            "operation": operation,
            "enabled": enabled,
            "reason_present": bool(reason.strip()) if isinstance(reason, str) else False,
        }
        try:
            self.audit_log.append(
                event_type="autonomy_permission",
                action="autonomy.permission.change",
                outcome="requested",
                actor="local_owner",
                details=audit_details,
            )
        except Exception as exc:
            raise PersistenceIntegrityError(
                "Autonomy permission change was blocked because its audit event could not be persisted"
            ) from exc

        def mutate(document):
            self._validate_document(document)
            document["permissions"][operation] = {
                "enabled": enabled,
                "updated_at": timestamp,
                "reason": reason.strip() if isinstance(reason, str) else None,
            }
            self._append_event(
                document,
                operation,
                "permission_granted" if enabled else "permission_revoked",
            )
            self._validate_document(document)
            return dict(document["permissions"][operation])

        record = self.store.update(mutate, default=self._empty_document())
        try:
            self.audit_log.append(
                event_type="autonomy_permission",
                action="autonomy.permission.change",
                outcome="completed",
                actor="local_owner",
                details=audit_details,
            )
        except Exception:
            return {
                "success": False,
                "code": "permission_audit_completion_failed",
                "operation": operation,
                "permission": record,
                "side_effect_may_have_occurred": True,
            }
        return {"success": True, "operation": operation, "permission": record}

    def authorize(self, operation: str, *, autonomous: bool) -> dict:
        operation = self._operation(operation)
        if not isinstance(autonomous, bool):
            return {
                "allowed": False,
                "operation": operation,
                "code": "invalid_autonomy_mode",
                "message": "Autonomy mode must be an explicit boolean.",
            }
        if not autonomous:
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

    def record_state(
        self,
        operation: str,
        state: str,
        *,
        run_id: str | None = None,
        detail: str | None = None,
    ) -> dict:
        operation = self._operation(operation)
        if not isinstance(state, str) or not state.strip() or len(state) > 40:
            raise ValueError("state must contain 1-40 characters")
        if run_id is not None and (
            not isinstance(run_id, str) or not run_id.strip() or len(run_id) > 128
        ):
            raise ValueError("run_id must contain 1-128 characters")
        if detail is not None and (not isinstance(detail, str) or len(detail) > 500):
            raise ValueError("detail must be at most 500 characters")
        event = {
            "event_id": uuid4().hex,
            "operation": operation,
            "state": state.strip(),
            "run_id": run_id.strip() if isinstance(run_id, str) else None,
            "detail": detail,
            "timestamp": self._now(),
        }

        def mutate(document):
            self._validate_document(document)
            self._append_event(document, operation, event["state"], event)
            self._validate_document(document)
            return dict(event)

        return self.store.update(mutate, default=self._empty_document())

    @staticmethod
    def _append_event(
        document: dict,
        operation: str,
        state: str,
        event: dict | None = None,
    ) -> None:
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
