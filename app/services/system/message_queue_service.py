"""Durable bounded work queue with atomic claims, leases, retries and dead letters."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from threading import RLock
from typing import Any
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.sessions.session_manager_service import redact_sensitive_text, redact_sensitive_value


class MessageQueueService:
    MAX_MESSAGES = 2000
    MAX_BODY_CHARS = 20000
    MAX_ATTEMPTS = 5
    LEASE_SECONDS = 300
    STATUSES = {"queued", "running", "completed", "dead_letter"}

    def __init__(self, storage_path: str = "memory/message_queue.json"):
        self.store = AtomicJsonStore(storage_path)
        self.store.read_or_create({"schema_version": 1, "messages": []})
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _validate(cls, document: Any) -> list[dict]:
        if not isinstance(document, dict) or document.get("schema_version") != 1:
            raise PersistenceIntegrityError("message queue schema is invalid")
        messages = document.get("messages")
        if not isinstance(messages, list) or len(messages) > cls.MAX_MESSAGES:
            raise PersistenceIntegrityError("message queue list is invalid")
        ids = set()
        for item in messages:
            if not isinstance(item, dict):
                raise PersistenceIntegrityError("message record is invalid")
            mid = item.get("message_id")
            if not isinstance(mid, str) or not mid or mid in ids:
                raise PersistenceIntegrityError("message ID is invalid or duplicated")
            ids.add(mid)
            if not isinstance(item.get("status"), str) or item.get("status") not in cls.STATUSES:
                raise PersistenceIntegrityError("message status is invalid")
            if (
                not isinstance(item.get("topic"), str)
                or not item["topic"].strip()
                or len(item["topic"]) > 128
                or not isinstance(item.get("body"), dict)
                or not isinstance(item.get("max_attempts"), int)
                or isinstance(item.get("max_attempts"), bool)
                or not 1 <= item["max_attempts"] <= cls.MAX_ATTEMPTS
                or not isinstance(item.get("attempts"), int)
                or isinstance(item.get("attempts"), bool)
                or not 0 <= item["attempts"] <= item["max_attempts"]
            ):
                raise PersistenceIntegrityError("message body, topic or attempt limits are invalid")
        return messages

    def enqueue(self, topic: str, body: dict[str, Any], *, dedupe_key: str | None = None, max_attempts: int = 3) -> dict:
        if not isinstance(topic, str) or not topic.strip() or len(topic) > 128:
            return {"success": False, "code": "invalid_topic"}
        if (
            not isinstance(body, dict)
            or not isinstance(max_attempts, int)
            or isinstance(max_attempts, bool)
            or not 1 <= max_attempts <= self.MAX_ATTEMPTS
            or (
                dedupe_key is not None
                and (
                    not isinstance(dedupe_key, str)
                    or not dedupe_key.strip()
                    or len(dedupe_key) > 256
                )
            )
        ):
            return {"success": False, "code": "invalid_message"}
        try:
            import json
            body = redact_sensitive_value(body)
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False)
            if len(encoded) > self.MAX_BODY_CHARS:
                return {"success": False, "code": "message_too_large"}
        except (TypeError, ValueError, RecursionError):
            return {"success": False, "code": "message_not_json"}
        now = self._now()
        message = {
            "message_id": str(uuid4()), "topic": topic.strip(), "body": body,
            "dedupe_key": dedupe_key, "status": "queued", "attempts": 0,
            "max_attempts": max_attempts, "created_at": now.isoformat(),
            "updated_at": now.isoformat(), "available_at": now.isoformat(),
            "lease_until": None, "last_error": None,
        }

        def insert(document):
            messages = self._validate(document)
            if dedupe_key:
                existing = next((m for m in messages if m.get("dedupe_key") == dedupe_key and m.get("status") in {"queued", "running", "completed"}), None)
                if existing:
                    return {"duplicate": True, "message": dict(existing)}
            if len(messages) >= self.MAX_MESSAGES:
                terminal = next((i for i, m in enumerate(messages) if m["status"] in {"completed", "dead_letter"}), None)
                if terminal is None:
                    return {"error": "queue_capacity_reached"}
                messages.pop(terminal)
            messages.append(message)
            return {"duplicate": False, "message": dict(message)}

        try:
            result = self.store.update(insert, {"schema_version": 1, "messages": []})
        except Exception:
            return {"success": False, "code": "queue_storage_unavailable"}
        if "error" in result:
            return {"success": False, "code": result["error"]}
        return {"success": True, **result}

    def claim(self, topic: str | None = None) -> dict:
        now = self._now()
        now_text = now.isoformat()
        def claim_one(document):
            messages = self._validate(document)
            # Expired leases return to the queue, but consume the previous attempt.
            for item in messages:
                if item["status"] == "running":
                    try:
                        expired = datetime.fromisoformat(item["lease_until"]) <= now
                    except (TypeError, ValueError):
                        expired = True
                    if expired or not item.get("lease_token"):
                        item["status"] = "dead_letter" if item["attempts"] >= item["max_attempts"] else "queued"
                        item["last_error"] = "worker_lease_expired" if item.get("lease_token") else "legacy_lease_recovered"
                        item["updated_at"] = now_text
                        item["lease_until"] = None
                        item["lease_token"] = None
            for item in messages:
                if item["status"] != "queued" or (topic is not None and item["topic"] != topic):
                    continue
                try:
                    due = datetime.fromisoformat(item["available_at"]) <= now
                except (TypeError, ValueError):
                    due = False
                if not due:
                    continue
                item["status"] = "running"
                item["attempts"] += 1
                item["updated_at"] = now_text
                item["lease_until"] = (now + timedelta(seconds=self.LEASE_SECONDS)).isoformat()
                item["lease_token"] = secrets.token_urlsafe(32)
                return dict(item)
            return None
        try:
            item = self.store.update(claim_one, {"schema_version": 1, "messages": []})
        except Exception:
            return {"success": False, "code": "queue_storage_unavailable"}
        return {"success": True, "message": item, "claimed": item is not None}

    def acknowledge(self, message_id: str, *, lease_token: str, success: bool, error: str | None = None, retry_delay_seconds: int = 30) -> dict:
        if (
            not isinstance(message_id, str) or not message_id
            or not isinstance(lease_token, str) or not lease_token or len(lease_token) > 128
            or not isinstance(success, bool)
        ):
            return {"success": False, "code": "invalid_acknowledgement"}
        if not isinstance(retry_delay_seconds, int) or isinstance(retry_delay_seconds, bool) or not 0 <= retry_delay_seconds <= 86400:
            return {"success": False, "code": "invalid_retry_delay"}
        now = self._now()
        def finish(document):
            messages = self._validate(document)
            item = next((m for m in messages if m["message_id"] == message_id), None)
            if item is None:
                return {"error": "message_not_found"}
            if item["status"] != "running":
                return {"error": "message_not_claimed"}
            stored_token = item.get("lease_token")
            if not isinstance(stored_token, str) or not secrets.compare_digest(stored_token, lease_token):
                return {"error": "invalid_lease_token"}
            item["updated_at"] = now.isoformat()
            item["lease_until"] = None
            item["lease_token"] = None
            if success:
                item["status"] = "completed"
                item["last_error"] = None
            else:
                safe_error = redact_sensitive_text(str(error or "worker_failed"))[:500]
                item["last_error"] = safe_error
                if item["attempts"] >= item["max_attempts"]:
                    item["status"] = "dead_letter"
                else:
                    item["status"] = "queued"
                    item["available_at"] = (now + timedelta(seconds=retry_delay_seconds)).isoformat()
            return dict(item)
        try:
            result = self.store.update(finish, {"schema_version": 1, "messages": []})
        except Exception:
            return {"success": False, "code": "queue_storage_unavailable"}
        return {"success": "error" not in result, "message": result if "error" not in result else None, "code": result.get("error")}

    def list(self, status: str | None = None, limit: int = 100) -> dict:
        if status is not None and status not in self.STATUSES:
            return {"success": False, "code": "invalid_status", "messages": []}
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            return {"success": False, "code": "invalid_limit", "messages": []}
        try:
            messages = list(self._validate(self.store.read({"schema_version": 1, "messages": []})))
        except Exception:
            return {"success": False, "code": "queue_storage_unavailable", "messages": []}
        filtered = [m for m in messages if status is None or m["status"] == status]
        # Lease tokens are bearer capabilities: return them only to the caller
        # that atomically claims a message, never through general list APIs.
        visible = [
            {key: value for key, value in item.items() if key != "lease_token"}
            for item in filtered[-limit:]
        ]
        return {"success": True, "messages": visible, "count": len(filtered)}
