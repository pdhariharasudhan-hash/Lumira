from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64
MAX_EVENTS = 10_000
_SENSITIVE_KEY = re.compile(r"password|secret|token|credential|api[_-]?key|authorization|file.?path", re.I)


class SecurityAuditLogService:
    """Append-only, hash-chained security events with fail-closed integrity checks.

    The hash chain detects accidental or partial tampering. It is not a substitute
    for a separately protected signing key or remote immutable storage.
    """

    def __init__(self, path: str | Path = "memory/security_audit_log.json") -> None:
        self.store = AtomicJsonStore(path)

    def append(
        self,
        *,
        event_type: str,
        action: str,
        outcome: str,
        actor: str = "system",
        details: dict | None = None,
    ) -> dict:
        event_type = self._required_text(event_type, "event_type", 80)
        action = self._required_text(action, "action", 100)
        outcome = self._required_text(outcome, "outcome", 40)
        actor = self._required_text(actor, "actor", 100)
        safe_details = self._safe_details(details)

        def mutate(document: dict) -> dict:
            self._validate_document(document)
            self._verify_document(document)
            events = document["events"]
            if len(events) >= MAX_EVENTS:
                raise PersistenceIntegrityError("Security audit log reached its configured capacity")
            previous_hash = events[-1]["hash"] if events else GENESIS_HASH
            record = {
                "sequence": len(events) + 1,
                "event_id": uuid4().hex,
                "timestamp": datetime.now(UTC).isoformat(),
                "event_type": event_type,
                "action": action,
                "outcome": outcome,
                "actor": actor,
                "details": safe_details,
                "previous_hash": previous_hash,
            }
            record["hash"] = self._digest(record)
            events.append(record)
            document["last_hash"] = record["hash"]
            return record

        return self.store.update(mutate, default=self._empty_document())

    def verify_integrity(self) -> dict:
        try:
            document = self.store.read(default=self._empty_document())
            self._validate_document(document)
            self._verify_document(document)
            return {
                "valid": True,
                "event_count": len(document["events"]),
                "last_hash": document["last_hash"],
            }
        except (PersistenceIntegrityError, OSError, TypeError, ValueError):
            return {"valid": False, "event_count": 0, "code": "audit_integrity_error"}

    def recent_events(self, limit: int = 50) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        document = self.store.read(default=self._empty_document())
        self._validate_document(document)
        self._verify_document(document)
        return document["events"][-limit:]

    @staticmethod
    def _empty_document() -> dict:
        return {"schema_version": SCHEMA_VERSION, "events": [], "last_hash": GENESIS_HASH}

    @staticmethod
    def _required_text(value: str, name: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
            raise ValueError(f"{name} must contain 1-{maximum} characters")
        return value.strip()

    @classmethod
    def _safe_details(cls, details: dict | None) -> dict:
        if details is None:
            return {}
        if not isinstance(details, dict):
            raise ValueError("details must be an object")
        safe = {}
        for key, value in list(details.items())[:20]:
            if not isinstance(key, str) or _SENSITIVE_KEY.search(key):
                continue
            if isinstance(value, str):
                safe[key[:60]] = value[:200]
            elif isinstance(value, (int, float, bool)) or value is None:
                safe[key[:60]] = value
            elif isinstance(value, list):
                safe[key[:60]] = [
                    item[:120] if isinstance(item, str) else item
                    for item in value[:20]
                    if isinstance(item, (str, int, float, bool)) or item is None
                ]
        encoded = json.dumps(safe, ensure_ascii=False, allow_nan=False)
        if len(encoded) > 2_000:
            raise ValueError("details exceed the audit event size limit")
        return safe

    @staticmethod
    def _digest(record: dict) -> str:
        payload = {key: value for key, value in record.items() if key != "hash"}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _validate_document(cls, document: dict) -> None:
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != SCHEMA_VERSION
            or not isinstance(document.get("events"), list)
            or len(document["events"]) > MAX_EVENTS
            or not isinstance(document.get("last_hash"), str)
        ):
            raise PersistenceIntegrityError("Invalid security audit document")

    @classmethod
    def _verify_document(cls, document: dict) -> None:
        previous_hash = GENESIS_HASH
        for index, event in enumerate(document["events"], start=1):
            if (
                not isinstance(event, dict)
                or event.get("sequence") != index
                or event.get("previous_hash") != previous_hash
                or not isinstance(event.get("hash"), str)
                or event["hash"] != cls._digest(event)
            ):
                raise PersistenceIntegrityError("Security audit hash chain verification failed")
            previous_hash = event["hash"]
        if document["last_hash"] != previous_hash:
            raise PersistenceIntegrityError("Security audit head hash does not match")
