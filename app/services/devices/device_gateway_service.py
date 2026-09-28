import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.providers.provider_registry import ProviderRegistry
from app.services.sessions.session_manager_service import redact_sensitive_value


class DeviceTransport(Protocol):
    def send_command(self, device_id: str, device_type: str, action: str, payload: dict) -> dict:
        """Send one bounded command through a configured physical-device adapter."""


class DeviceGatewayService:
    """Versioned, bounded hardware boundary; device interfaces contain no AI policy."""

    DEVICE_TYPES = {
        "raspberry_pi", "esp32", "arduino", "robotics", "cyberdeck", "smart_glasses",
        "mobile", "camera", "microphone", "sensor", "bluetooth", "wifi", "smart_home", "vehicle",
    }
    MESSAGE_TYPES = {"telemetry", "heartbeat", "command_result"}
    MAX_PAYLOAD_BYTES = 64_000
    MAX_MESSAGES = 200
    STORE_SCHEMA_VERSION = 1

    def __init__(self, transport: DeviceTransport | None = None, path: str | Path = "memory/device_messages.json"):
        self.transport = ProviderRegistry.get("device_transport") if transport is None else transport
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        if not self.path.exists():
            self.store.write({"schema_version": self.STORE_SCHEMA_VERSION, "messages": []})

    @classmethod
    def _validate_envelope(cls, envelope: dict) -> tuple[str, str, str, dict]:
        if not isinstance(envelope, dict):
            raise ValueError("Device message must be an object")
        device_id = envelope.get("device_id")
        device_type = envelope.get("device_type")
        message_type = envelope.get("message_type")
        message_id = envelope.get("message_id")
        payload = envelope.get("payload", {})
        if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", device_id):
            raise ValueError("device_id is invalid")
        if not isinstance(device_type, str) or device_type not in cls.DEVICE_TYPES:
            raise ValueError("device_type is unsupported")
        if not isinstance(message_type, str) or message_type not in cls.MESSAGE_TYPES:
            raise ValueError("message_type is unsupported")
        if message_id is not None and (not isinstance(message_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", message_id)):
            raise ValueError("message_id is invalid")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        try:
            payload_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("payload must contain valid JSON data") from exc
        if payload_size > cls.MAX_PAYLOAD_BYTES:
            raise ValueError(f"payload exceeds {cls.MAX_PAYLOAD_BYTES} bytes")
        return device_id, device_type, message_type, payload

    @classmethod
    def _validate_store(cls, document: object) -> dict:
        if not isinstance(document, dict) or document.get("schema_version") != cls.STORE_SCHEMA_VERSION or not isinstance(document.get("messages"), list):
            raise PersistenceIntegrityError("Device message store has an invalid schema")
        if len(document["messages"]) > cls.MAX_MESSAGES:
            raise PersistenceIntegrityError("Device message store exceeds its retention limit")
        for message in document["messages"]:
            if not isinstance(message, dict) or not isinstance(message.get("message_id"), str) or not isinstance(message.get("payload"), dict):
                raise PersistenceIntegrityError("Device message record is invalid")
        return document

    def receive(self, envelope: dict) -> dict:
        device_id, device_type, message_type, payload = self._validate_envelope(envelope)
        message_id = envelope.get("message_id") or str(uuid4())
        message = {
            "schema_version": 1,
            "message_id": message_id,
            "owner_id": "local",
            "device_id": device_id,
            "device_type": device_type,
            "message_type": message_type,
            "client_timestamp": envelope.get("timestamp") if isinstance(envelope.get("timestamp"), str) and len(envelope["timestamp"]) <= 80 else None,
            "received_at": datetime.now(UTC).isoformat(),
            "payload": redact_sensitive_value(payload),
            "status": "received",
        }

        def append(document):
            self._validate_store(document)
            existing = next((item for item in document["messages"] if item.get("device_id") == device_id and item.get("message_id") == message_id), None)
            if existing:
                return {"message": existing, "duplicate": True}
            document["messages"].append(message)
            document["messages"] = document["messages"][-self.MAX_MESSAGES:]
            return {"message": message, "duplicate": False}

        return self.store.update(append, {"schema_version": self.STORE_SCHEMA_VERSION, "messages": []})

    def list_messages(self, limit: int = 50) -> list[dict]:
        if not 0 <= limit <= self.MAX_MESSAGES:
            raise ValueError(f"limit must be between 0 and {self.MAX_MESSAGES}")
        document = self._validate_store(self.store.read({"schema_version": self.STORE_SCHEMA_VERSION, "messages": []}))
        return list(reversed(document["messages"][-limit:])) if limit else []

    def send_command(self, device_id: str, device_type: str, action: str, payload: dict | None = None) -> dict:
        if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", device_id):
            return {"success": False, "code": "invalid_device_id", "message": "device_id is invalid."}
        if not isinstance(device_type, str) or device_type not in self.DEVICE_TYPES:
            return {"success": False, "code": "unsupported_device_type", "message": "device_type is unsupported."}
        if not isinstance(action, str) or not action.strip() or len(action) > 100:
            return {"success": False, "code": "invalid_action", "message": "Action must contain 1 to 100 characters."}
        if payload is None:
            payload = {}
        try:
            if not isinstance(payload, dict) or len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > self.MAX_PAYLOAD_BYTES:
                return {"success": False, "code": "invalid_payload", "message": "Command payload must be an object of at most 64000 bytes."}
        except (TypeError, ValueError, RecursionError):
            return {"success": False, "code": "invalid_payload", "message": "Command payload must contain valid JSON data."}
        if self.transport is None:
            return {"success": False, "code": "provider_unavailable", "message": "No device transport is configured; no command was sent."}
        try:
            result = self.transport.send_command(device_id, device_type, action.strip(), redact_sensitive_value(payload))
        except Exception:
            return {"success": False, "code": "provider_error", "message": "The device transport failed; command delivery is unconfirmed."}
        if not isinstance(result, dict) or result.get("success") is not True:
            return {"success": False, "code": "command_unconfirmed", "message": "The device transport did not confirm command delivery."}
        command_id = result.get("command_id")
        if not isinstance(command_id, str) or not command_id or len(command_id) > 128:
            return {"success": False, "code": "invalid_provider_response", "message": "The device transport must return a command identifier to confirm delivery."}
        return {"success": True, "status": "sent", "command_id": command_id, "device_id": device_id, "device_type": device_type}
