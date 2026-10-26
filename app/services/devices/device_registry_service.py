"""Bounded persistent registry for Lumira-compatible devices.

Registration describes a device; it does not establish a live connection or
authorize physical commands. Command transport remains a separate provider.
"""
import re
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class DeviceRegistryService:
    SCHEMA_VERSION = 1
    MAX_DEVICES = 200
    MAX_CAPABILITIES = 30
    MAX_PERMISSIONS = 20
    DEVICE_TYPES = {
        "raspberry_pi", "esp32", "arduino", "robotics", "cyberdeck",
        "smart_glasses", "mobile", "camera", "microphone", "sensor",
        "bluetooth", "wifi", "smart_home", "vehicle",
    }
    STATUSES = {"registered", "online", "offline", "maintenance"}
    PERMISSIONS = {
        "telemetry.read", "commands.receive", "camera.capture",
        "microphone.capture", "robot.motion", "smart_home.control",
        "vehicle.read", "files.read", "files.write",
    }

    def __init__(self, path: str | Path = "memory/devices.json"):
        self.path = Path(path)
        self.store = AtomicJsonStore(path)
        if not self.path.exists():
            self.store.write({"schema_version": self.SCHEMA_VERSION, "devices": []})

    @classmethod
    def _validate_store(cls, value: object) -> dict:
        if not isinstance(value, dict) or value.get("schema_version") != cls.SCHEMA_VERSION:
            raise PersistenceIntegrityError("Device registry schema is invalid")
        devices = value.get("devices")
        if not isinstance(devices, list) or len(devices) > cls.MAX_DEVICES:
            raise PersistenceIntegrityError("Device registry list is invalid")
        seen = set()
        for device in devices:
            if not isinstance(device, dict):
                raise PersistenceIntegrityError("Device registry record is invalid")
            device_id = device.get("device_id")
            if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", device_id) or device_id in seen:
                raise PersistenceIntegrityError("Device registry ID is invalid or duplicated")
            seen.add(device_id)
            owner_id = device.get("owner_id", "local")
            if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 128:
                raise PersistenceIntegrityError("Device registry owner identifier is invalid")
            for timestamp_field in ("registered_at", "updated_at"):
                timestamp_value = device.get(timestamp_field)
                if not isinstance(timestamp_value, str) or not timestamp_value or len(timestamp_value) > 40:
                    raise PersistenceIntegrityError("Device registry timestamp is invalid")
            last_seen = device.get("last_seen")
            if last_seen is not None and (not isinstance(last_seen, str) or len(last_seen) > 40):
                raise PersistenceIntegrityError("Device registry last-seen timestamp is invalid")
            if not isinstance(device.get("device_type"), str) or device.get("device_type") not in cls.DEVICE_TYPES or not isinstance(device.get("status"), str) or device.get("status") not in cls.STATUSES:
                raise PersistenceIntegrityError("Device registry type or status is invalid")
            capabilities = device.get("capabilities", [])
            permissions = device.get("permissions", [])
            if not isinstance(capabilities, list) or len(capabilities) > cls.MAX_CAPABILITIES:
                raise PersistenceIntegrityError("Device registry capabilities are invalid")
            if not isinstance(permissions, list) or len(permissions) > cls.MAX_PERMISSIONS:
                raise PersistenceIntegrityError("Device registry permissions are invalid")
            if any(not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", item) for item in capabilities):
                raise PersistenceIntegrityError("Device registry contains an invalid capability")
            if len(set(capabilities)) != len(capabilities):
                raise PersistenceIntegrityError("Device registry contains duplicate capabilities")
            if any(not isinstance(item, str) or item not in cls.PERMISSIONS for item in permissions):
                raise PersistenceIntegrityError("Device registry contains an unsupported permission")
            if len(set(permissions)) != len(permissions):
                raise PersistenceIntegrityError("Device registry contains duplicate permissions")
            if not isinstance(device.get("connection"), str) or device.get("connection") not in {"unverified", "local", "wifi", "bluetooth", "usb", "serial", "cloud"}:
                raise PersistenceIntegrityError("Device registry connection type is invalid")
        return value

    @classmethod
    def _validate_strings(cls, values: list[str], limit: int, field: str) -> list[str]:
        if not isinstance(values, list) or len(values) > limit:
            raise ValueError(f"{field} must contain at most {limit} entries")
        cleaned = []
        for value in values:
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", value):
                raise ValueError(f"{field} entries must be short identifier strings")
            if value not in cleaned:
                cleaned.append(value)
        return cleaned

    def register_device(
        self,
        device_id: str,
        device_type: str,
        capabilities: list[str] | None = None,
        permissions: list[str] | None = None,
        connection: str = "unverified",
        status: str = "registered",
    ) -> dict:
        if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", device_id):
            raise ValueError("device_id is invalid")
        if not isinstance(device_type, str) or device_type not in self.DEVICE_TYPES:
            raise ValueError("device_type is unsupported")
        if not isinstance(status, str) or status not in self.STATUSES or status == "online":
            raise ValueError("new devices cannot be marked online until a valid device message is received")
        if not isinstance(connection, str) or connection not in {"unverified", "local", "wifi", "bluetooth", "usb", "serial", "cloud"}:
            raise ValueError("connection type is unsupported")
        capabilities = self._validate_strings(capabilities or [], self.MAX_CAPABILITIES, "capabilities")
        permissions = self._validate_strings(permissions or [], self.MAX_PERMISSIONS, "permissions")
        unknown = sorted(set(permissions) - self.PERMISSIONS)
        if unknown:
            raise ValueError("Unsupported device permissions: " + ", ".join(unknown))
        now = datetime.now(UTC).isoformat()
        record = {
            "device_id": device_id,
            "owner_id": "local",
            "device_type": device_type,
            "capabilities": capabilities,
            "status": status,
            "connection": connection,
            "permissions": permissions,
            "registered_at": now,
            "updated_at": now,
            "last_seen": None,
        }

        def mutate(document):
            self._validate_store(document)
            existing = next((item for item in document["devices"] if item.get("device_id") == device_id), None)
            if existing:
                if existing.get("device_type") != device_type:
                    raise ValueError("A registered device cannot change its device_type")
                record["registered_at"] = existing.get("registered_at", now)
                record["last_seen"] = existing.get("last_seen")
                document["devices"].remove(existing)
            elif len(document["devices"]) >= self.MAX_DEVICES:
                raise ValueError("Device registry has reached its retention limit")
            document["devices"].append(record)
            return deepcopy(record)

        return self.store.update(mutate, {"schema_version": self.SCHEMA_VERSION, "devices": []})

    def list_devices(self, status: str | None = None, device_type: str | None = None, limit: int = 100) -> list[dict]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= self.MAX_DEVICES:
            raise ValueError(f"limit must be between 0 and {self.MAX_DEVICES}")
        if status is not None and (not isinstance(status, str) or status not in self.STATUSES):
            raise ValueError("device status is unsupported")
        if device_type is not None and (not isinstance(device_type, str) or device_type not in self.DEVICE_TYPES):
            raise ValueError("device_type is unsupported")
        document = self._validate_store(self.store.read({"schema_version": self.SCHEMA_VERSION, "devices": []}))
        devices = document["devices"]
        if status:
            devices = [item for item in devices if item.get("status") == status]
        if device_type:
            devices = [item for item in devices if item.get("device_type") == device_type]
        return deepcopy(sorted(devices, key=lambda item: item.get("updated_at", ""), reverse=True)[:limit])

    def is_recently_seen(self, device_id: str, max_age_seconds: int = 120) -> bool:
        """Return true only for an online registry record with a fresh received-message timestamp."""
        if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool) or not 1 <= max_age_seconds <= 3600:
            raise ValueError("max_age_seconds must be between 1 and 3600")
        document = self._validate_store(self.store.read({"schema_version": self.SCHEMA_VERSION, "devices": []}))
        device = next((item for item in document["devices"] if item.get("device_id") == device_id), None)
        if device is None or device.get("status") != "online":
            return False
        last_seen = device.get("last_seen")
        if not isinstance(last_seen, str):
            return False
        try:
            seen_at = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            if seen_at.tzinfo is None:
                seen_at = seen_at.replace(tzinfo=UTC)
        except ValueError:
            return False
        age = datetime.now(UTC) - seen_at.astimezone(UTC)
        return timedelta(0) <= age <= timedelta(seconds=max_age_seconds)

    def record_message_seen(self, device_id: str, device_type: str) -> bool:
        """Mark a registered device online only after a valid message is received."""
        now = datetime.now(UTC).isoformat()
        found = {"value": False}

        def mutate(document):
            self._validate_store(document)
            device = next((item for item in document["devices"] if item.get("device_id") == device_id), None)
            if device is None or device.get("device_type") != device_type:
                return False
            device["status"] = "online"
            device["last_seen"] = now
            device["updated_at"] = now
            found["value"] = True
            return True

        self.store.update(mutate, {"schema_version": self.SCHEMA_VERSION, "devices": []})
        return found["value"]

    def update_status(self, device_id: str, status: str) -> dict:
        if not isinstance(status, str) or status not in self.STATUSES or status == "online":
            raise ValueError("manual status must be registered, offline, or maintenance; online requires a valid device message")
        now = datetime.now(UTC).isoformat()
        result = {}

        def mutate(document):
            self._validate_store(document)
            device = next((item for item in document["devices"] if item.get("device_id") == device_id), None)
            if device is None:
                raise KeyError("device not found")
            device["status"] = status
            device["updated_at"] = now
            if status == "online":
                device["last_seen"] = now
            result.update(deepcopy(device))
            return True

        self.store.update(mutate, {"schema_version": self.SCHEMA_VERSION, "devices": []})
        return result
