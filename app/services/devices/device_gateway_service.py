"""Versioned, bounded hardware boundary with independent device authorization."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.providers.provider_registry import ProviderRegistry
from app.services.providers.provider_access_policy_service import (
    ProviderAccessDenied,
    ProviderAccessPolicyService,
)
from app.services.sessions.session_manager_service import redact_sensitive_value
from app.services.devices.device_registry_service import DeviceRegistryService
from app.services.security.security_audit_log_service import SecurityAuditLogService
from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService


class DeviceTransport(Protocol):
    def send_command(self, device_id: str, device_type: str, action: str, payload: dict) -> dict:
        """Send one bounded command through a configured physical-device adapter."""


class DeviceGatewayService:
    """Device messages and commands are bounded, authorized and auditable."""

    DEVICE_TYPES = {
        "raspberry_pi", "esp32", "arduino", "robotics", "cyberdeck", "smart_glasses",
        "mobile", "camera", "microphone", "sensor", "bluetooth", "wifi", "smart_home",
        "vehicle", "drone", "laptop", "raspberry_pi_pico", "wearable", "smart_display",
        "printer", "other",
    }
    MESSAGE_TYPES = {"telemetry", "heartbeat", "command_result"}
    SENSITIVE_PERMISSIONS = {
        "camera.capture", "microphone.capture", "audio.output", "robot.motion",
        "smart_home.control", "vehicle.read", "files.read", "files.write",
        "system.command",
    }
    MAX_PAYLOAD_BYTES = 64_000
    MAX_MESSAGES = 200
    STORE_SCHEMA_VERSION = 1

    def __init__(
        self,
        transport: DeviceTransport | None = None,
        path: str | Path = "memory/device_messages.json",
        *,
        provider_policy=None,
        device_registry=None,
        audit_log=None,
        autonomy_permissions=None,
    ):
        self.transport = ProviderRegistry.get("device_transport") if transport is None else transport
        self.provider_policy = provider_policy or ProviderAccessPolicyService()
        self.registry = device_registry or DeviceRegistryService()
        self.audit_log = audit_log or SecurityAuditLogService()
        self.autonomy_permissions = autonomy_permissions or AutonomyPermissionService(audit_log=self.audit_log)
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        self.store.read_or_create({
            "schema_version": self.STORE_SCHEMA_VERSION,
            "messages": [],
        })

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
        if message_id is not None and (
            not isinstance(message_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", message_id)
        ):
            raise ValueError("message_id is invalid")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        try:
            payload_size = len(
                json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            )
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("payload must contain valid JSON data") from exc
        if payload_size > cls.MAX_PAYLOAD_BYTES:
            raise ValueError(f"payload exceeds {cls.MAX_PAYLOAD_BYTES} bytes")
        return device_id, device_type, message_type, payload

    @classmethod
    def _validate_store(cls, document: object) -> dict:
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != cls.STORE_SCHEMA_VERSION
            or not isinstance(document.get("messages"), list)
        ):
            raise PersistenceIntegrityError("Device message store has an invalid schema")
        if len(document["messages"]) > cls.MAX_MESSAGES:
            raise PersistenceIntegrityError("Device message store exceeds its retention limit")
        seen = set()
        for message in document["messages"]:
            if (
                not isinstance(message, dict)
                or not isinstance(message.get("message_id"), str)
                or not isinstance(message.get("device_id"), str)
                or not isinstance(message.get("payload"), dict)
            ):
                raise PersistenceIntegrityError("Device message record is invalid")
            key = (message["device_id"], message["message_id"])
            if key in seen:
                raise PersistenceIntegrityError("Device message store contains duplicate message IDs")
            seen.add(key)
        return document

    def receive(self, envelope: dict) -> dict:
        device_id, device_type, message_type, payload = self._validate_envelope(envelope)
        core_context = envelope.get("core_context")
        if core_context is not None and not isinstance(core_context, dict):
            raise ValueError("core_context must be an object")
        message_id = envelope.get("message_id") or str(uuid4())
        message = {
            "schema_version": 1,
            "message_id": message_id,
            "owner_id": "local",
            "device_id": device_id,
            "device_type": device_type,
            "message_type": message_type,
            "client_timestamp": (
                envelope.get("timestamp")
                if isinstance(envelope.get("timestamp"), str)
                and len(envelope["timestamp"]) <= 80
                else None
            ),
            "received_at": datetime.now(UTC).isoformat(),
            "payload": redact_sensitive_value(payload),
            "status": "received",
            "core_context": (
                redact_sensitive_value(core_context)
                if isinstance(core_context, dict)
                else None
            ),
        }

        def append(document):
            self._validate_store(document)
            existing = next(
                (
                    item for item in document["messages"]
                    if item.get("device_id") == device_id
                    and item.get("message_id") == message_id
                ),
                None,
            )
            if existing:
                return {"message": existing, "duplicate": True}
            document["messages"].append(message)
            document["messages"] = document["messages"][-self.MAX_MESSAGES:]
            return {"message": message, "duplicate": False}

        return self.store.update(
            append,
            {"schema_version": self.STORE_SCHEMA_VERSION, "messages": []},
        )

    def list_messages(self, limit: int = 50) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= self.MAX_MESSAGES:
            raise ValueError(f"limit must be between 0 and {self.MAX_MESSAGES}")
        document = self._validate_store(
            self.store.read({"schema_version": self.STORE_SCHEMA_VERSION, "messages": []})
        )
        return list(reversed(document["messages"][-limit:])) if limit else []

    @classmethod
    def _required_sensitive_permission(cls, action: str) -> str | None:
        """Map action namespaces to explicit device permissions; never trust naming aliases."""
        if action in cls.SENSITIVE_PERMISSIONS:
            return action
        namespace = action.split(".", 1)[0].lower()
        if namespace == "robot":
            return "robot.motion"
        if namespace == "camera":
            return "camera.capture"
        if namespace == "microphone":
            return "microphone.capture"
        if namespace == "audio":
            operation = action.split(".", 1)[1].lower() if "." in action else ""
            if operation in {"output", "playback", "play", "speak", "tts", "synthesis"}:
                return "audio.output"
            if operation in {"capture", "record", "listen", "transcribe", "recognize", "input"}:
                return "microphone.capture"
            # Unknown audio operations are conservatively treated as capture.
            return "microphone.capture"
        if namespace in {"smart_home", "home"}:
            return "smart_home.control"
        if namespace == "vehicle":
            return "vehicle.read"
        if namespace == "files":
            parts = action.split(".")
            operation = parts[1].lower() if len(parts) > 1 else ""
            if operation in {"read", "list", "search", "download", "stat"}:
                return "files.read"
            # Unknown file operations fail toward the more restrictive write grant.
            return "files.write"
        if namespace in {"shell", "process", "terminal", "system"}:
            return "system.command"
        return None

    def _authorize_device(self, device_id: str, device_type: str, action: str) -> dict | None:
        try:
            devices = self.registry.list_devices(limit=self.registry.MAX_DEVICES)
            device = next(
                (item for item in devices if item.get("device_id") == device_id),
                None,
            )
            if device is None:
                return {"success": False, "code": "device_not_registered"}
            if device.get("device_type") != device_type:
                return {"success": False, "code": "device_type_mismatch"}
            if device.get("status") != "online" or not self.registry.is_recently_seen(device_id):
                return {"success": False, "code": "device_heartbeat_stale"}
            permissions = device.get("permissions", [])
            capabilities = device.get("capabilities", [])
            if (
                not isinstance(permissions, list)
                or any(not isinstance(value, str) for value in permissions)
                or not isinstance(capabilities, list)
                or any(not isinstance(value, str) for value in capabilities)
            ):
                return {"success": False, "code": "device_authorization_record_invalid"}
            if "commands.receive" not in permissions:
                return {"success": False, "code": "device_command_permission_missing"}
            if action not in capabilities:
                return {"success": False, "code": "device_capability_not_declared"}
            required_permission = self._required_sensitive_permission(action)
            if required_permission and required_permission not in permissions:
                return {
                    "success": False,
                    "code": "device_sensitive_permission_missing",
                    "required_permission": required_permission,
                }
            return None
        except Exception:
            return {"success": False, "code": "device_authorization_unavailable"}

    def _audit_command(
        self,
        *,
        device_id: str,
        action: str,
        outcome: str,
        payload: dict,
        code: str,
    ) -> bool:
        fingerprint = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        try:
            self.audit_log.append(
                event_type="device_command",
                action="device.command",
                outcome=outcome,
                actor="local_owner",
                details={
                    "device_id": device_id,
                    "capability": action,
                    "payload_sha256": fingerprint,
                    "result_code": code,
                },
            )
            return True
        except Exception:
            return False

    def send_command(
        self,
        device_id: str,
        device_type: str,
        action: str,
        payload: dict | None = None,
        *,
        autonomous: bool = False,
    ) -> dict:
        if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", device_id):
            return {"success": False, "code": "invalid_device_id", "message": "device_id is invalid."}
        if not isinstance(device_type, str) or device_type not in self.DEVICE_TYPES:
            return {"success": False, "code": "unsupported_device_type", "message": "device_type is unsupported."}
        if not isinstance(action, str) or not action.strip() or len(action) > 100:
            return {"success": False, "code": "invalid_action", "message": "Action must contain 1 to 100 characters."}
        action = action.strip()
        if not isinstance(autonomous, bool):
            return {"success": False, "code": "invalid_autonomy_mode"}
        if autonomous:
            try:
                authorization = self.autonomy_permissions.authorize(
                    "device.command",
                    autonomous=True,
                )
            except Exception:
                return {"success": False, "code": "autonomous_permission_state_unavailable"}
            if authorization.get("allowed") is not True:
                return {
                    "success": False,
                    "code": authorization.get("code", "autonomous_permission_required"),
                    "message": authorization.get("message", "Autonomous device commands are not authorized."),
                }
        if payload is None:
            payload = {}
        try:
            encoded_payload = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
            if not isinstance(payload, dict) or len(encoded_payload) > self.MAX_PAYLOAD_BYTES:
                return {"success": False, "code": "invalid_payload", "message": "Command payload must be an object of at most 64000 bytes."}
        except (TypeError, ValueError, RecursionError):
            return {"success": False, "code": "invalid_payload", "message": "Command payload must contain valid JSON data."}

        authorization = self._authorize_device(device_id, device_type, action)
        if authorization is not None:
            self._audit_command(
                device_id=device_id,
                action=action,
                outcome="denied",
                payload=payload,
                code=authorization["code"],
            )
            return authorization
        if self.transport is None:
            return {"success": False, "code": "provider_unavailable", "message": "No device transport is configured; no command was sent."}
        if not self._audit_command(
            device_id=device_id,
            action=action,
            outcome="started",
            payload=payload,
            code="started",
        ):
            return {
                "success": False,
                "code": "security_audit_unavailable",
                "message": "Device command was blocked because its security audit event could not be persisted.",
            }
        try:
            self.provider_policy.authorize(self.transport, "device command transport")
            result = self.transport.send_command(
                device_id,
                device_type,
                action,
                redact_sensitive_value(payload),
            )
        except ProviderAccessDenied as error:
            result = {"success": False, "code": error.code, "message": error.user_message}
        except Exception:
            result = {
                "success": False,
                "code": "provider_error",
                "message": "The device transport failed; command delivery is unconfirmed.",
            }

        if not isinstance(result, dict) or result.get("success") is not True:
            code = result.get("code", "command_unconfirmed") if isinstance(result, dict) else "invalid_provider_response"
            self._audit_command(
                device_id=device_id,
                action=action,
                outcome="failed",
                payload=payload,
                code=str(code),
            )
            return {
                "success": False,
                "code": "command_unconfirmed",
                "message": "The device transport did not confirm command delivery.",
            }
        command_id = result.get("command_id")
        if not isinstance(command_id, str) or not command_id or len(command_id) > 128:
            self._audit_command(
                device_id=device_id,
                action=action,
                outcome="failed",
                payload=payload,
                code="invalid_provider_response",
            )
            return {
                "success": False,
                "code": "invalid_provider_response",
                "message": "The device transport must return a command identifier to confirm delivery.",
            }
        if not self._audit_command(
            device_id=device_id,
            action=action,
            outcome="completed",
            payload=payload,
            code="confirmed",
        ):
            return {
                "success": False,
                "code": "device_outcome_audit_failed",
                "message": "The device returned a command ID, but Lumira could not persist the final security audit event.",
                "side_effect_may_have_occurred": True,
            }
        return {
            "success": True,
            "status": "sent",
            "command_id": command_id,
            "device_id": device_id,
            "device_type": device_type,
        }
