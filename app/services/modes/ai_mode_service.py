from __future__ import annotations

from pathlib import Path
from app.services.persistence.atomic_json_store import AtomicJsonStore


class AIModeService:
    MODES = {
        "offline": {"network_allowed": False, "external_providers_allowed": False},
        "hybrid": {"network_allowed": True, "external_providers_allowed": True},
        "cloud": {"network_allowed": True, "external_providers_allowed": True},
    }

    def __init__(self, path: str | Path = "memory/ai_mode.json"):
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        if not self.path.exists():
            self.store.write({"schema_version": 1, "mode": "offline"})

    def get(self) -> dict:
        data = self.store.read({"schema_version": 1, "mode": "offline"})
        mode = data.get("mode", "offline")
        if mode not in self.MODES:
            mode = "offline"
        return {"mode": mode, **self.MODES[mode]}

    def set(self, mode: str) -> dict:
        if mode not in self.MODES:
            raise ValueError("mode must be offline, hybrid or cloud")
        def update(data):
            data["schema_version"] = 1
            data["mode"] = mode
            return self.get_record(mode)
        return self.store.update(update, {"schema_version": 1, "mode": "offline"})

    def get_record(self, mode: str) -> dict:
        return {"mode": mode, **self.MODES[mode]}
