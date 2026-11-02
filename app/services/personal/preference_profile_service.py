from __future__ import annotations

from pathlib import Path
from app.services.persistence.atomic_json_store import AtomicJsonStore


class PreferenceProfileService:
    """User-controlled preferences; no automatic inference changes are made."""

    MAX_KEY = 100
    MAX_VALUE = 5000

    def __init__(self, path: str | Path = "memory/preference_profile.json"):
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        if not self.path.exists():
            self.store.write({"schema_version": 1, "preferences": {}})

    def list(self) -> dict:
        data = self.store.read({"schema_version": 1, "preferences": {}})
        prefs = data.get("preferences", {})
        return dict(prefs) if isinstance(prefs, dict) else {}

    def set(self, key: str, value: str) -> dict:
        if not isinstance(key, str) or not key.strip() or len(key.strip()) > self.MAX_KEY:
            raise ValueError("key must contain 1 to 100 characters")
        if not isinstance(value, str) or len(value) > self.MAX_VALUE:
            raise ValueError("value must contain at most 5000 characters")
        key = key.strip()
        def update(data):
            prefs = data.setdefault("preferences", {})
            prefs[key] = value
            return {"key": key, "value": value}
        return self.store.update(update, {"schema_version": 1, "preferences": {}})

    def remove(self, key: str) -> bool:
        if not isinstance(key, str) or not key.strip() or len(key.strip()) > self.MAX_KEY:
            raise ValueError("key must contain 1 to 100 characters")
        removed = {"value": False}
        def update(data):
            prefs = data.setdefault("preferences", {})
            removed["value"] = prefs.pop(key.strip(), None) is not None
            return removed["value"]
        self.store.update(update, {"schema_version": 1, "preferences": {}})
        return removed["value"]
