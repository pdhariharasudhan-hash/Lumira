import json
from pathlib import Path
from typing import Dict, Any


CORE_FEATURES = {
    "memory",
    "voice_input"
}


class FeatureRegistryService:

    def __init__(
        self,
        registry_path: str = "memory/feature_registry.json"
    ):
        self.registry_path = Path(
            registry_path
        )

        self._ensure_registry()

    def _default_registry(
        self
    ) -> Dict[str, Any]:

        return {

            "memory": {
                "enabled": True,
                "version": "1.0",
                "category": "core"
            },

            "voice_input": {
                "enabled": True,
                "version": "1.0",
                "category": "core"
            },

            "voice_idea_capture": {
                "enabled": False,
                "version": "1.0",
                "category": "capture"
            },

            "artifact_manager": {
                "enabled": False,
                "version": "1.0",
                "category": "artifact"
            },

            "image_generation": {
                "enabled": False,
                "version": "1.0",
                "category": "artifact"
            },

            "unified_search": {
                "enabled": False,
                "version": "1.0",
                "category": "search"
            }
        }

    def _ensure_registry(
        self
    ):

        self.registry_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.registry_path.exists():

            self.registry_path.write_text(
                json.dumps(
                    self._default_registry(),
                    indent=2
                ),
                encoding="utf-8"
            )

    def _read(
        self
    ) -> Dict[str, Any]:

        self._ensure_registry()

        try:

            content = (
                self.registry_path.read_text(
                    encoding="utf-8"
                )
            )

            if not content.strip():

                data = (
                    self._default_registry()
                )

                self._write(
                    data
                )

                return data

            return json.loads(
                content
            )

        except Exception:

            data = (
                self._default_registry()
            )

            self._write(
                data
            )

            return data

    def _write(
        self,
        data: Dict[str, Any]
    ):

        self.registry_path.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    def get_all(
        self
    ):

        return self._read()

    def get_feature(
        self,
        feature_name: str
    ):

        registry = self._read()

        return registry.get(
            feature_name
        )

    def feature_exists(
        self,
        feature_name: str
    ) -> bool:

        registry = self._read()

        return (
            feature_name
            in registry
        )

    def is_enabled(
        self,
        feature_name: str
    ) -> bool:

        feature = (
            self.get_feature(
                feature_name
            )
        )

        if not feature:
            return False

        return bool(
            feature.get(
                "enabled",
                False
            )
        )

    def enable(
        self,
        feature_name: str
    ) -> bool:

        registry = self._read()

        if feature_name not in registry:
            return False

        registry[
            feature_name
        ]["enabled"] = True

        self._write(
            registry
        )

        return True

    def disable(
        self,
        feature_name: str
    ) -> bool:

        registry = self._read()

        if feature_name not in registry:
            return False

        if feature_name in CORE_FEATURES:
            return False

        registry[
            feature_name
        ]["enabled"] = False

        self._write(
            registry
        )

        return True

    def register(
        self,
        feature_name: str,
        metadata: Dict[str, Any]
    ):

        registry = self._read()

        registry[
            feature_name
        ] = metadata

        self._write(
            registry
        )

        return registry[
            feature_name
        ]

    def unregister(
        self,
        feature_name: str
    ) -> bool:

        registry = self._read()

        if feature_name not in registry:
            return False

        if feature_name in CORE_FEATURES:
            return False

        del registry[
            feature_name
        ]

        self._write(
            registry
        )

        return True