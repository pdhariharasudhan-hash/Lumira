from __future__ import annotations

from pathlib import Path
from app.services.persistence.atomic_json_store import AtomicJsonStore


class DeviceProfileService:
    """Stores non-secret profiles for the user's personal hardware projects."""

    SUPPORTED = {"laptop", "raspberry_pi", "esp32", "raspberry_pi_pico", "cyberdeck", "robot", "drone", "smart_home", "other"}

    def __init__(self, path: str | Path = "memory/device_profiles.json"):
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        if not self.path.exists(): self.store.write({"schema_version": 1, "profiles": {}})

    def register(self, profile_id: str, device_type: str, metadata: dict | None = None) -> dict:
        if not isinstance(profile_id, str) or not profile_id.strip() or len(profile_id.strip()) > 128:
            raise ValueError("profile_id must contain 1 to 128 characters")
        if device_type not in self.SUPPORTED: raise ValueError("unsupported device type")
        if metadata is not None and (not isinstance(metadata, dict) or len(metadata) > 50):
            raise ValueError("metadata must be an object with at most 50 fields")
        profile_id = profile_id.strip()
        profile = {"profile_id": profile_id, "device_type": device_type, "metadata": metadata or {}, "connection": "unverified"}
        def update(data):
            data.setdefault("profiles", {})[profile_id] = profile
            return profile
        return self.store.update(update, {"schema_version": 1, "profiles": {}})

    def list(self) -> list[dict]:
        data = self.store.read({"schema_version": 1, "profiles": {}})
        return [dict(x) for x in data.get("profiles", {}).values() if isinstance(x, dict)]
