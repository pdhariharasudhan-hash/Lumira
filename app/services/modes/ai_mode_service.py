from __future__ import annotations

from pathlib import Path

from app.services.persistence.atomic_json_store import AtomicJsonStore


class AIModeService:
    """Persist the user's local/cloud policy independently from task-category modes."""

    MODES = {
        "offline": {"local_providers_allowed": True},
        "hybrid": {"local_providers_allowed": True},
        "cloud": {"local_providers_allowed": False},
    }
    DEFAULT_MODE = "hybrid"

    def __init__(self, path: str | Path = "memory/ai_mode.json"):
        self.store = AtomicJsonStore(path)
        self.path = Path(path)
        if not self.path.exists():
            self.store.write({
                "schema_version": 1,
                "mode": self.DEFAULT_MODE,
                "cloud_enabled": False,
            })

    def get(self) -> dict:
        data = self.store.read({
            "schema_version": 1,
            "mode": self.DEFAULT_MODE,
            "cloud_enabled": False,
        })
        if not isinstance(data, dict):
            raise ValueError("AI mode settings must contain a JSON object.")
        mode = data.get("mode", self.DEFAULT_MODE)
        if not isinstance(mode, str) or mode not in self.MODES:
            raise ValueError("AI mode settings contain an invalid mode.")
        cloud_enabled = data.get("cloud_enabled", False) is True
        external_allowed = mode != "offline" and cloud_enabled
        return {
            "mode": mode,
            "cloud_enabled": cloud_enabled,
            "local_providers_allowed": self.MODES[mode]["local_providers_allowed"],
            "network_allowed": external_allowed,
            "external_providers_allowed": external_allowed,
        }

    def set(self, mode: str) -> dict:
        if not isinstance(mode, str) or mode not in self.MODES:
            raise ValueError("mode must be offline, hybrid or cloud")

        def update(data):
            if not isinstance(data, dict):
                raise ValueError("AI mode settings must contain a JSON object.")
            data["schema_version"] = 1
            data["mode"] = mode
            data.setdefault("cloud_enabled", False)
            return self.get_record(mode, data.get("cloud_enabled") is True)

        return self.store.update(
            update,
            {"schema_version": 1, "mode": self.DEFAULT_MODE, "cloud_enabled": False},
        )

    def set_cloud_enabled(self, enabled: bool) -> dict:
        if type(enabled) is not bool:
            raise ValueError("cloud_enabled must be a boolean.")

        def update(data):
            if not isinstance(data, dict):
                raise ValueError("AI mode settings must contain a JSON object.")
            mode = data.get("mode", self.DEFAULT_MODE)
            if not isinstance(mode, str) or mode not in self.MODES:
                raise ValueError("AI mode settings contain an invalid mode.")
            data["schema_version"] = 1
            data["mode"] = mode
            data["cloud_enabled"] = enabled
            return self.get_record(mode, enabled)

        return self.store.update(
            update,
            {"schema_version": 1, "mode": self.DEFAULT_MODE, "cloud_enabled": False},
        )

    def get_record(self, mode: str, cloud_enabled: bool = False) -> dict:
        external_allowed = mode != "offline" and cloud_enabled is True
        return {
            "mode": mode,
            "cloud_enabled": cloud_enabled is True,
            "local_providers_allowed": self.MODES[mode]["local_providers_allowed"],
            "network_allowed": external_allowed,
            "external_providers_allowed": external_allowed,
        }
