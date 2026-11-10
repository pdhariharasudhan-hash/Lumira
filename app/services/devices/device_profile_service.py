from __future__ import annotations
import json
import math
import re
from pathlib import Path
from app.services.persistence.atomic_json_store import AtomicJsonStore


class DeviceProfileService:
    """Stores bounded, non-secret metadata for the user's hardware projects."""
    SUPPORTED = {"laptop", "raspberry_pi", "esp32", "arduino", "raspberry_pi_pico", "cyberdeck",
                 "robot", "robotics", "drone", "smart_home", "smart_glasses", "wearable",
                 "smart_display", "printer", "vehicle", "mobile", "camera", "microphone",
                 "sensor", "bluetooth", "wifi", "other"}
    MAX_METADATA_BYTES = 16_000
    SECRET_KEY = re.compile(r"password|secret|token|api.?key|credential|private.?key", re.I)

    def __init__(self, path: str | Path = "memory/device_profiles.json"):
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        if not self.path.exists():
            self.store.write({"schema_version": 1, "profiles": {}})

    @classmethod
    def _validate_metadata(cls, metadata):
        if metadata is None:
            return {}
        if not isinstance(metadata, dict) or len(metadata) > 50:
            raise ValueError("metadata must be an object with at most 50 fields")
        try:
            encoded = json.dumps(metadata, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("metadata must contain finite JSON values") from exc
        if len(encoded) > cls.MAX_METADATA_BYTES:
            raise ValueError("metadata exceeds 16000 bytes")
        def inspect(value, depth=0):
            if depth > 5:
                raise ValueError("metadata nesting exceeds five levels")
            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, str) or len(key) > 80 or cls.SECRET_KEY.search(key):
                        raise ValueError("metadata keys must be short and must not contain credentials or secrets")
                    inspect(item, depth + 1)
            elif isinstance(value, list):
                if len(value) > 100:
                    raise ValueError("metadata arrays may contain at most 100 entries")
                for item in value:
                    inspect(item, depth + 1)
            elif isinstance(value, float) and not math.isfinite(value):
                raise ValueError("metadata numbers must be finite")
            elif not isinstance(value, (str, int, float, bool, type(None))):
                raise ValueError("metadata must contain JSON-compatible values")
            elif isinstance(value, str) and len(value) > 2000:
                raise ValueError("metadata text values may contain at most 2000 characters")
        inspect(metadata)
        return metadata

    def register(self, profile_id: str, device_type: str, metadata: dict | None = None) -> dict:
        if not isinstance(profile_id, str) or not profile_id.strip() or len(profile_id.strip()) > 128:
            raise ValueError("profile_id must contain 1 to 128 characters")
        if device_type not in self.SUPPORTED:
            raise ValueError("unsupported device type")
        metadata = self._validate_metadata(metadata)
        profile_id = profile_id.strip()
        profile = {"profile_id": profile_id, "device_type": device_type, "metadata": metadata, "connection": "unverified"}
        def update(data):
            if not isinstance(data, dict) or not isinstance(data.get("profiles", {}), dict):
                raise ValueError("device profile store is invalid")
            data.setdefault("schema_version", 1)
            data.setdefault("profiles", {})[profile_id] = profile
            return dict(profile)
        return self.store.update(update, {"schema_version": 1, "profiles": {}})

    def list(self) -> list[dict]:
        data = self.store.read({"schema_version": 1, "profiles": {}})
        if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
            raise ValueError("device profile store is invalid")
        return [dict(x) for x in data["profiles"].values() if isinstance(x, dict)]
