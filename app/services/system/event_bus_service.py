"""Bounded durable event bus with in-process subscribers and replayable history."""
from __future__ import annotations

import json
import re
import inspect
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.sessions.session_manager_service import redact_sensitive_value


class EventBusService:
    MAX_EVENTS = 5000
    _subscriber_registry: dict[str, dict[str, list[Callable[[dict[str, Any]], Any]]]] = {}
    _shared_lock = RLock()
    MAX_EVENT_NAME = 128
    MAX_SOURCE = 128
    MAX_PAYLOAD_BYTES = 64 * 1024
    _name_pattern = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")

    def __init__(self, storage_path: str = "memory/event_bus.json"):
        self.store = AtomicJsonStore(storage_path)
        self.store.read_or_create({"schema_version": 1, "events": []})
        # Subscribers are process-local and scoped to this event-store path.
        self._lock = self._shared_lock
        key = str(Path(storage_path).resolve())
        with self._lock:
            self._subscribers = self._subscriber_registry.setdefault(key, {})

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _validate_document(cls, document: Any) -> list[dict]:
        if not isinstance(document, dict) or document.get("schema_version") != 1:
            raise PersistenceIntegrityError("event bus schema is invalid")
        events = document.get("events")
        if not isinstance(events, list) or len(events) > cls.MAX_EVENTS:
            raise PersistenceIntegrityError("event bus event list is invalid")
        seen = set()
        for item in events:
            if not isinstance(item, dict):
                raise PersistenceIntegrityError("event bus contains an invalid event")
            event_id = item.get("event_id")
            name = item.get("name")
            if not isinstance(event_id, str) or not event_id or event_id in seen:
                raise PersistenceIntegrityError("event bus contains duplicate or invalid IDs")
            seen.add(event_id)
            if not isinstance(name, str) or not cls._name_pattern.fullmatch(name):
                raise PersistenceIntegrityError("event bus contains an invalid event name")
            if (
                not isinstance(item.get("payload"), dict)
                or not isinstance(item.get("source"), str)
                or not item["source"].strip()
                or len(item["source"]) > cls.MAX_SOURCE
                or not isinstance(item.get("created_at"), str)
            ):
                raise PersistenceIntegrityError("event bus event shape is invalid")
            try:
                encoded = json.dumps(item["payload"], ensure_ascii=False, allow_nan=False)
            except (TypeError, ValueError, RecursionError) as exc:
                raise PersistenceIntegrityError("event bus payload is not valid JSON") from exc
            if len(encoded.encode("utf-8")) > cls.MAX_PAYLOAD_BYTES:
                raise PersistenceIntegrityError("event bus payload exceeds its storage limit")
        return events

    def subscribe(self, event_name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        if not isinstance(event_name, str) or not self._name_pattern.fullmatch(event_name):
            raise ValueError("event_name is invalid")
        if not callable(handler) or inspect.iscoroutinefunction(handler):
            raise ValueError("handler must be a synchronous callable; async consumers must use the durable queue")
        with self._lock:
            self._subscribers.setdefault(event_name, []).append(handler)

    def unsubscribe(self, event_name: str, handler: Callable[[dict[str, Any]], Any]) -> bool:
        with self._lock:
            handlers = self._subscribers.get(event_name, [])
            try:
                handlers.remove(handler)
            except ValueError:
                return False
            if not handlers:
                self._subscribers.pop(event_name, None)
            return True

    def publish(self, event_name: str, payload: dict[str, Any] | None = None, *, source: str = "local") -> dict:
        if not isinstance(event_name, str) or not self._name_pattern.fullmatch(event_name):
            return {"success": False, "code": "invalid_event_name"}
        if not isinstance(source, str) or not source.strip() or len(source) > self.MAX_SOURCE:
            return {"success": False, "code": "invalid_event_source"}
        data = {} if payload is None else payload
        if not isinstance(data, dict):
            return {"success": False, "code": "invalid_event_payload"}
        try:
            data = redact_sensitive_value(data)
            if not isinstance(data, dict):
                return {"success": False, "code": "invalid_event_payload"}
            encoded = json.dumps(data, ensure_ascii=False, allow_nan=False)
            if len(encoded.encode("utf-8")) > self.MAX_PAYLOAD_BYTES:
                return {"success": False, "code": "event_payload_too_large"}
        except (TypeError, ValueError, RecursionError):
            return {"success": False, "code": "event_payload_not_json"}
        event = {
            "event_id": str(uuid4()),
            "name": event_name,
            "source": source.strip(),
            "payload": data,
            "created_at": self._now(),
        }

        def append(document):
            events = self._validate_document(document)
            events.append(event)
            del events[:-self.MAX_EVENTS]
            return len(events)

        try:
            self.store.update(append, {"schema_version": 1, "events": []})
        except Exception:
            return {"success": False, "code": "event_persistence_failed"}
        delivery_errors = []
        with self._lock:
            handlers = list(self._subscribers.get(event_name, []))
        for handler in handlers:
            try:
                result = handler(dict(event))
                if inspect.isawaitable(result):
                    close = getattr(result, "close", None)
                    if callable(close):
                        close()
                    delivery_errors.append("async_handler_requires_async_dispatch")
            except Exception as exc:
                delivery_errors.append(type(exc).__name__)
        return {
            "success": True,
            "event": event,
            "subscriber_count": len(handlers),
            "delivery_errors": delivery_errors,
            "durable": True,
        }

    def list_events(self, *, name: str | None = None, after: str | None = None, limit: int = 100) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            return {"success": False, "code": "invalid_limit", "events": []}
        try:
            document = self.store.read({"schema_version": 1, "events": []})
            events = list(self._validate_document(document))
        except Exception:
            return {"success": False, "code": "event_store_unavailable", "events": []}
        if name is not None:
            if not isinstance(name, str) or not self._name_pattern.fullmatch(name):
                return {"success": False, "code": "invalid_event_name", "events": []}
            events = [item for item in events if item["name"] == name]
        if after is not None:
            index = next((i for i, item in enumerate(events) if item["event_id"] == after), None)
            if index is None:
                return {"success": False, "code": "cursor_not_found", "events": []}
            events = events[index + 1:]
        return {"success": True, "events": events[-limit:], "count": len(events), "durable": True}
