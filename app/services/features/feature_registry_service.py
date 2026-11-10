from copy import deepcopy
from pathlib import Path
import re
from typing import Any, Dict

from app.services.persistence.atomic_json_store import (
    AtomicJsonStore,
    PersistenceIntegrityError,
)
from app.services.providers.provider_registry import ProviderRegistry

FEATURE_STATES = {
    "AVAILABLE",
    "ENABLED",
    "DISABLED",
    "DEGRADED",
    "FAILED",
    "EXPERIMENTAL",
}

CORE_FEATURES = {"memory", "voice_input"}

# Provider-backed features must not be reported as activatable until their
# concrete provider is registered at application startup. This is separate
# from dependency readiness: a feature can have its dependencies installed
# while its external service remains unconfigured.
FEATURE_PROVIDER_REQUIREMENTS = {
    "voice_idea_capture": ("transcription",),
    "voice_transcript": ("transcription",),
    "image_understanding": ("image_understanding",),
    "image_generation": ("image_generation",),
    "research": ("research",),
}

FEATURE_CATALOG: Dict[str, Dict[str, Any]] = {
    "memory": {"version": "1.0", "category": "core", "status": "ENABLED", "dependencies": [], "capabilities": ["memory.get", "memory.store", "memory.search"], "configuration": {}, "permissions": ["memory.read", "memory.write"], "health": "healthy", "tests": True},
    "voice_input": {"version": "1.0", "category": "voice", "status": "ENABLED", "dependencies": [], "capabilities": ["voice.capture"], "configuration": {}, "permissions": ["microphone"], "health": "healthy", "tests": True},
    "intent": {"version": "1.0", "category": "core_intelligence", "status": "AVAILABLE", "dependencies": [], "capabilities": ["intent.classify"], "configuration": {}, "permissions": [], "health": "healthy", "tests": True},
    "goals": {"version": "1.0", "category": "core_intelligence", "status": "AVAILABLE", "dependencies": ["memory"], "capabilities": ["goals.create", "goals.update", "goals.list"], "configuration": {}, "permissions": ["memory.read", "memory.write"], "health": "healthy", "tests": True},
    "planner": {"version": "1.0", "category": "core_intelligence", "status": "AVAILABLE", "dependencies": ["goals"], "capabilities": ["planner.create", "planner.validate"], "configuration": {"max_tasks": 12}, "permissions": [], "health": "healthy", "tests": True},
    "agents": {"version": "1.0", "category": "core_intelligence", "status": "EXPERIMENTAL", "dependencies": ["planner"], "capabilities": ["agents.discover", "agents.select", "agents.execute"], "configuration": {"max_retries": 2}, "permissions": [], "health": "healthy", "tests": True},
    "learning": {"version": "1.0", "category": "memory", "status": "AVAILABLE", "dependencies": ["memory"], "capabilities": ["learning.analyze", "learning.lessons"], "configuration": {}, "permissions": ["memory.read", "memory.write"], "health": "healthy", "tests": True},
    "sessions": {"version": "1.0", "category": "memory", "status": "AVAILABLE", "dependencies": ["memory"], "capabilities": ["sessions.create", "sessions.resume", "sessions.recover"], "configuration": {}, "permissions": ["memory.read", "memory.write"], "health": "healthy", "tests": True},
    "projects": {"version": "1.0", "category": "execution", "status": "AVAILABLE", "dependencies": ["memory"], "capabilities": ["projects.create", "projects.inspect", "projects.versions"], "configuration": {}, "permissions": ["filesystem.project"], "health": "healthy", "tests": True},
    "code": {"version": "1.0", "category": "execution", "status": "AVAILABLE", "dependencies": ["projects"], "capabilities": ["code.generate", "code.modify", "code.test"], "configuration": {}, "permissions": ["filesystem.project"], "health": "healthy", "tests": True},
    "workflows": {"version": "1.0", "category": "execution", "status": "AVAILABLE", "dependencies": ["memory"], "capabilities": ["workflow.run", "workflow.recover"], "configuration": {"max_steps": 12}, "permissions": [], "health": "healthy", "tests": True},
    "autonomous_development": {"version": "1.0", "category": "execution", "status": "AVAILABLE", "dependencies": ["projects", "code", "workflows"], "capabilities": ["development.inspect", "development.change", "development.verify"], "configuration": {"max_iterations": 5}, "permissions": ["filesystem.project", "process.bounded"], "health": "healthy", "tests": True},
    "recovery": {"version": "1.0", "category": "execution", "status": "AVAILABLE", "dependencies": ["workflows"], "capabilities": ["recovery.resume", "recovery.inspect"], "configuration": {"max_resumes": 3}, "permissions": [], "health": "healthy", "tests": True},
    "artifact_manager": {"version": "1.0", "category": "multimodal", "status": "AVAILABLE", "dependencies": ["memory"], "capabilities": ["artifact.create", "artifact.search", "artifact.retrieve"], "configuration": {}, "permissions": ["filesystem.artifacts"], "health": "healthy", "tests": True},
    "unified_search": {"version": "1.0", "category": "multimodal", "status": "AVAILABLE", "dependencies": ["memory", "artifact_manager", "projects"], "capabilities": ["search.unified"], "configuration": {}, "permissions": ["memory.read", "filesystem.project", "filesystem.artifacts"], "health": "healthy", "tests": True},
    "voice_idea_capture": {"version": "1.0", "category": "voice", "status": "AVAILABLE", "dependencies": ["voice_input", "artifact_manager", "memory"], "capabilities": ["voice.record", "voice.transcribe", "voice.idea"], "configuration": {}, "permissions": ["microphone", "filesystem.artifacts"], "health": "healthy", "tests": True},
    "wake_word_handoff": {"version": "1.0", "category": "voice", "status": "AVAILABLE", "dependencies": ["voice_input"], "capabilities": ["voice.wake.start", "voice.wake.consume"], "configuration": {"max_pending_events": 20}, "permissions": ["microphone"], "health": "healthy", "tests": True},
        "voice_transcript": {"version": "1.0", "category": "voice", "status": "AVAILABLE", "dependencies": ["voice_input", "artifact_manager"], "capabilities": ["voice.transcribe", "voice.language"], "configuration": {}, "permissions": ["microphone", "filesystem.artifacts"], "health": "healthy", "tests": True},
    "audio_playback": {"version": "1.0", "category": "voice", "status": "AVAILABLE", "dependencies": ["voice_input", "artifact_manager"], "capabilities": ["audio.playback"], "configuration": {}, "permissions": ["filesystem.artifacts", "audio.output"], "health": "healthy", "tests": True},
    "idea_summarization": {"version": "1.0", "category": "voice", "status": "AVAILABLE", "dependencies": ["memory", "artifact_manager"], "capabilities": ["idea.summarize", "idea.store"], "configuration": {}, "permissions": ["memory.read", "memory.write", "filesystem.artifacts"], "health": "healthy", "tests": True},
    "image_understanding": {"version": "1.0", "category": "multimodal", "status": "EXPERIMENTAL", "dependencies": ["artifact_manager"], "capabilities": ["image.analyze", "image.ocr"], "configuration": {}, "permissions": ["filesystem.artifacts"], "health": "healthy", "tests": True},
    "image_generation": {"version": "1.0", "category": "multimodal", "status": "AVAILABLE", "dependencies": ["artifact_manager"], "capabilities": ["image.generate"], "configuration": {}, "permissions": ["filesystem.artifacts"], "health": "healthy", "tests": True},
    "web_access": {"version": "1.0", "category": "research", "status": "AVAILABLE", "dependencies": ["artifact_manager"], "capabilities": ["web.fetch", "web.process"], "configuration": {"max_response_bytes": 5000000, "max_redirects": 3}, "permissions": ["network.public_https"], "health": "healthy", "tests": True},
    "research": {"version": "1.0", "category": "research", "status": "AVAILABLE", "dependencies": ["web_access", "memory", "artifact_manager"], "capabilities": ["research.collect", "research.compare", "research.summarize"], "configuration": {}, "permissions": ["network.public_https", "memory.write"], "health": "healthy", "tests": True},
    "device_management": {"version": "1.0", "category": "devices", "status": "AVAILABLE", "dependencies": ["memory"], "capabilities": ["device.register", "device.status"], "configuration": {}, "permissions": [], "health": "healthy", "tests": True},
    "mode_management": {"version": "1.0", "category": "devices", "status": "AVAILABLE", "dependencies": [], "capabilities": ["mode.select", "mode.status"], "configuration": {}, "permissions": [], "health": "healthy", "tests": True},
    "terminal": {"version": "1.0", "category": "interface", "status": "AVAILABLE", "dependencies": ["projects"], "capabilities": ["terminal.test", "terminal.build"], "configuration": {"max_runs": 20, "timeout_seconds": 120}, "permissions": ["process.bounded"], "health": "healthy", "tests": True},
    "project_preview": {"version": "1.0", "category": "interface", "status": "AVAILABLE", "dependencies": ["projects"], "capabilities": ["preview.register", "preview.start", "preview.stop"], "configuration": {}, "permissions": ["network.localhost"], "health": "healthy", "tests": True},
    "notepad": {"version": "1.0", "category": "interface", "status": "AVAILABLE", "dependencies": ["memory"], "capabilities": ["notes.create", "notes.update", "notes.retrieve"], "configuration": {}, "permissions": ["memory.read", "memory.write"], "health": "healthy", "tests": True},
    "capability_system": {"version": "1.0", "category": "core", "status": "AVAILABLE", "dependencies": [], "capabilities": ["capability.discover", "capability.route"], "configuration": {}, "permissions": [], "health": "healthy", "tests": True},
    "security": {"version": "1.0", "category": "core", "status": "ENABLED", "dependencies": [], "capabilities": ["security.validate"], "configuration": {}, "permissions": [], "health": "healthy", "tests": True},
    "observability": {"version": "1.0", "category": "core", "status": "AVAILABLE", "dependencies": ["memory"], "capabilities": ["observability.status", "observability.history"], "configuration": {}, "permissions": [], "health": "healthy", "tests": True},
}


class FeatureRegistryService:
    """Persistent, dependency-aware feature lifecycle registry."""

    MAX_FEATURES = 100
    MAX_EXTENSION_NAME_LENGTH = 80
    MAX_LIST_ITEMS = 50
    MAX_METADATA_TEXT_LENGTH = 256

    FEATURE_ALIASES = {
        "voice_capture": "voice_idea_capture",
        "idea_capture": "voice_idea_capture",
        "transcript_generation": "voice_transcript",
        "audio_transcription": "voice_transcript",
        "idea_summary": "idea_summarization",
        "unified_search_service": "unified_search",
        "artifact_management": "artifact_manager",
        "project_previews": "project_preview",
    }

    def __init__(self, registry_path: str = "memory/feature_registry.json"):
        self.registry_path = registry_path
        self.store = AtomicJsonStore(registry_path)
        self._ensure_registry()

    @staticmethod
    def _default_registry() -> Dict[str, Any]:
        registry = {}
        for feature_id, metadata in FEATURE_CATALOG.items():
            item = deepcopy(metadata)
            item["feature_id"] = feature_id
            item["enabled"] = item["status"] == "ENABLED"
            registry[feature_id] = item
        return registry

    def _ensure_registry(self) -> None:
        current = self.store.read(default=None)
        if current is None:
            if Path(self.registry_path).exists():
                raise PersistenceIntegrityError(
                    "Feature registry contains JSON null; refusing to reset persisted state"
                )
            self.store.write(self._default_registry())
            return
        if not isinstance(current, dict):
            raise PersistenceIntegrityError(
                "Feature registry must be an object; refusing to reset persisted state"
            )
        if len(current) > self.MAX_FEATURES:
            raise PersistenceIntegrityError("Feature registry exceeds its record limit")
        changed = False
        defaults = self._default_registry()

        # Remove malformed unknown extension records and restore malformed catalog entries.
        for feature_id in list(current):
            if isinstance(current.get(feature_id), dict):
                continue
            if feature_id in defaults:
                current[feature_id] = deepcopy(defaults[feature_id])
            else:
                del current[feature_id]
            changed = True

        for feature_id, default in defaults.items():
            if feature_id not in current or not isinstance(current.get(feature_id), dict):
                # Repair only the malformed entry; preserve all other persisted feature state.
                current[feature_id] = deepcopy(default)
                changed = True
                continue

            item = current[feature_id]
            for key, value in default.items():
                if key not in item:
                    if key == "enabled":
                        item[key] = item.get("status") == "ENABLED"
                    else:
                        item[key] = deepcopy(value)
                    changed = True

            # Normalize structural fields before any dependency or lifecycle operation uses them.
            for key in ("dependencies", "capabilities", "permissions"):
                if not isinstance(item.get(key), list) or not all(
                    isinstance(value, str) and value.strip() for value in item[key]
                ):
                    item[key] = deepcopy(default[key])
                    changed = True
            if not isinstance(item.get("configuration"), dict):
                item["configuration"] = deepcopy(default["configuration"])
                changed = True
            status = item.get("status")
            if not isinstance(status, str) or status not in FEATURE_STATES:
                item["status"] = default["status"]
                changed = True
            health = item.get("health")
            if not isinstance(health, str) or health not in {"healthy", "degraded", "failed"}:
                item["health"] = default["health"]
                changed = True
            # A feature that is explicitly unhealthy must never remain enabled
            # merely because a persisted lifecycle flag is stale or corrupted.
            if item["health"] == "failed" and item["status"] == "ENABLED":
                item["status"] = "FAILED"
                changed = True
            if not isinstance(item.get("enabled"), bool):
                item["enabled"] = item["status"] == "ENABLED"
                changed = True
            # Persisted status and enabled flags must describe the same lifecycle state.
            # Keep status as the source of truth so corrupt data cannot silently activate
            # an AVAILABLE/FAILED feature or hide one marked ENABLED.
            expected_enabled = item["status"] == "ENABLED"
            if item["enabled"] != expected_enabled:
                item["enabled"] = expected_enabled
                changed = True

        if changed:
            self.store.write(current)

    @staticmethod
    def _normalize_name(feature_name: Any) -> str | None:
        """Canonicalize feature IDs and human-readable names identically."""
        if not isinstance(feature_name, str):
            return None
        normalized = re.sub(r"[\s-]+", "_", feature_name.strip().lower())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        if not normalized:
            return None
        return FeatureRegistryService.FEATURE_ALIASES.get(normalized, normalized)

    def _read(self) -> Dict[str, Any]:
        self._ensure_registry()
        data = self.store.read(default={})
        if not isinstance(data, dict):
            raise PersistenceIntegrityError("Feature registry must be an object")
        return data

    def get_all(self) -> Dict[str, Any]:
        return self._read()

    def list_features(self) -> Dict[str, Any]:
        registry = self._read()
        enabled = sorted(name for name, item in registry.items() if item.get("status") == "ENABLED")
        available = sorted(name for name, item in registry.items() if item.get("status") == "AVAILABLE")
        failed = sorted(name for name, item in registry.items() if item.get("status") == "FAILED")
        return {"count": len(registry), "enabled": enabled, "available": available, "failed": failed}

    def get_feature(self, feature_name: str) -> Dict[str, Any] | None:
        name = self._normalize_name(feature_name)
        return self._read().get(name) if name else None

    def feature_exists(self, feature_name: str) -> bool:
        name = self._normalize_name(feature_name)
        return bool(name and name in self._read())

    def is_enabled(self, feature_name: str) -> bool:
        feature = self.get_feature(feature_name)
        return bool(feature and feature.get("enabled", False))

    def dependencies(self, feature_name: str) -> list[str]:
        feature = self.get_feature(feature_name)
        return list(feature.get("dependencies", [])) if feature else []

    def can_enable(self, feature_name: str) -> tuple[bool, list[str]]:
        name = self._normalize_name(feature_name)
        if not name:
            return False, ["invalid feature name"]
        registry = self._read()
        feature = registry.get(name)
        if not feature:
            return False, [f"unknown feature: {name}"]
        if name == "terminal":
            return False, [
                "verified OS-level sandbox is not currently available; terminal activation is blocked"
            ]

        # Use one persisted snapshot so concurrent registry updates cannot make
        # a single readiness decision combine multiple inconsistent states.
        blockers: list[str] = []
        visited: set[str] = set()

        def inspect(feature_id: str, chain: tuple[str, ...]) -> None:
            if feature_id in chain:
                cycle = " -> ".join((*chain, feature_id))
                blockers.append(f"feature dependency cycle detected: {cycle}")
                return
            # The terminal safety gate must also apply when terminal appears
            # transitively in another feature's dependency graph.
            if feature_id == "terminal":
                blockers.append(
                    "verified OS-level sandbox is not implemented; terminal activation is blocked"
                )
                return
            if feature_id in visited:
                return
            visited.add(feature_id)

            item = registry.get(feature_id)
            if item is None:
                blockers.append(f"unknown feature dependency: {feature_id}")
                return
            health = item.get("health")
            if not isinstance(health, str) or health not in {"healthy", "degraded"}:
                blockers.append(f"feature health is {health}: {feature_id}")

            for provider_name in FEATURE_PROVIDER_REQUIREMENTS.get(feature_id, ()):
                if ProviderRegistry.get(provider_name) is None:
                    if provider_name == "image_understanding":
                        blockers.append(
                            "image-understanding provider is not configured; use either "
                            "LUMIRA_VISION_ENABLED=1 with LUMIRA_VISION_API_KEY, or "
                            "LUMIRA_OLLAMA_VISION_ENABLED=1 with a local Ollama vision model"
                        )
                    else:
                        blockers.append(
                            f"required provider is not configured: {provider_name} "
                            f"(feature: {feature_id})"
                        )

            next_chain = (*chain, feature_id)
            for dependency in item.get("dependencies", []):
                dependency_item = registry.get(dependency)
                if not dependency_item or dependency_item.get("enabled") is not True:
                    blockers.append(
                        "dependency is not enabled: " + " -> ".join((*next_chain, dependency))
                    )
                    continue
                inspect(dependency, next_chain)

        inspect(name, ())
        # A dependency may be reachable through more than one branch. Keep the
        # response deterministic and avoid repeating the same blocker.
        blockers = list(dict.fromkeys(blockers))
        return not blockers, blockers

    def can_enable_many(self, feature_names: list[str]) -> tuple[bool, list[str], list[str]]:
        """Check a complete dependency-ordered activation without changing persisted state."""
        if not isinstance(feature_names, list) or not feature_names:
            return False, ["activation order must be a non-empty list"], []
        ordered = []
        for raw_name in feature_names:
            name = self._normalize_name(raw_name)
            if not name:
                return False, ["invalid feature name in activation order"], []
            if name not in ordered:
                ordered.append(name)

        registry = self._read()
        selected = set(ordered)
        completed = set()
        blockers = []
        for name in ordered:
            if name == "terminal":
                blockers.append("verified OS-level sandbox is not currently available; terminal activation is blocked")
                continue
            item = registry.get(name)
            if item is None:
                blockers.append(f"unknown feature: {name}")
                continue
            if item.get("health") not in {"healthy", "degraded"} or item.get("status") == "FAILED":
                blockers.append(f"feature is not healthy enough to activate: {name}")
            for provider_name in FEATURE_PROVIDER_REQUIREMENTS.get(name, ()):
                if ProviderRegistry.get(provider_name) is None:
                    blockers.append(f"required provider is not configured: {provider_name} (feature: {name})")
            for dependency in item.get("dependencies", []):
                dependency_item = registry.get(dependency)
                if dependency_item is None:
                    blockers.append(f"unknown feature dependency: {name} -> {dependency}")
                elif dependency in selected:
                    if dependency not in completed and dependency_item.get("enabled") is not True:
                        blockers.append(f"activation order is invalid: {dependency} must precede {name}")
                elif dependency_item.get("enabled") is not True:
                    blockers.append(f"dependency is not enabled: {name} -> {dependency}")
            completed.add(name)
        blockers = list(dict.fromkeys(blockers))
        return not blockers, blockers, ordered

    def enable_many(self, feature_names: list[str]) -> tuple[bool, list[str], list[str]]:
        """Preflight and persist a dependency-ordered activation as one registry write."""
        if not isinstance(feature_names, list) or not feature_names:
            return False, ["activation order must be a non-empty list"], []

        ordered = []
        for raw_name in feature_names:
            name = self._normalize_name(raw_name)
            if not name:
                return False, ["invalid feature name in activation order"], []
            if name not in ordered:
                ordered.append(name)

        registry = self._read()
        selected = set(ordered)
        completed = set()
        blockers = []

        for name in ordered:
            if name == "terminal":
                blockers.append("verified OS-level sandbox is not currently available; terminal activation is blocked")
                continue
            item = registry.get(name)
            if item is None:
                blockers.append(f"unknown feature: {name}")
                continue
            health = item.get("health")
            if health not in {"healthy", "degraded"} or item.get("status") == "FAILED":
                blockers.append(f"feature is not healthy enough to activate: {name}")
            for provider_name in FEATURE_PROVIDER_REQUIREMENTS.get(name, ()):
                if ProviderRegistry.get(provider_name) is None:
                    blockers.append(f"required provider is not configured: {provider_name} (feature: {name})")
            for dependency in item.get("dependencies", []):
                dependency_item = registry.get(dependency)
                if dependency_item is None:
                    blockers.append(f"unknown feature dependency: {name} -> {dependency}")
                elif dependency in selected:
                    if dependency not in completed and dependency_item.get("enabled") is not True:
                        blockers.append(f"activation order is invalid: {dependency} must precede {name}")
                elif dependency_item.get("enabled") is not True:
                    blockers.append(f"dependency is not enabled: {name} -> {dependency}")
            completed.add(name)

        blockers = list(dict.fromkeys(blockers))
        if blockers:
            return False, blockers, []

        activated = []
        for name in ordered:
            item = registry[name]
            if item.get("enabled") is True and item.get("status") == "ENABLED":
                continue
            item["enabled"] = True
            item["status"] = "ENABLED"
            activated.append(name)

        if activated:
            self.store.write(registry)
        return True, [], activated

    def enable(self, feature_name: str) -> tuple[bool, list[str]]:
        name = self._normalize_name(feature_name)
        if not name:
            return False, ["invalid feature name"]
        registry = self._read()
        if name not in registry:
            return False, [f"unknown feature: {name}"]
        allowed, blockers = self.can_enable(name)
        if not allowed:
            return False, blockers
        registry[name]["enabled"] = True
        registry[name]["status"] = "ENABLED"
        self.store.write(registry)
        return True, []

    def disable(self, feature_name: str) -> tuple[bool, list[str]]:
        name = self._normalize_name(feature_name)
        if not name:
            return False, ["invalid feature name"]
        registry = self._read()
        if name not in registry:
            return False, [f"unknown feature: {name}"]
        if name in CORE_FEATURES:
            return False, [f"{name} is a protected core feature"]
        dependents = [
            dependent_name for dependent_name, item in registry.items()
            if name in item.get("dependencies", []) and item.get("enabled", False)
        ]
        if dependents:
            return False, [f"enabled dependents: {', '.join(sorted(dependents))}"]
        registry[name]["enabled"] = False
        registry[name]["status"] = "DISABLED"
        self.store.write(registry)
        return True, []

    def update_health(self, feature_name: str, health: str) -> bool:
        if not isinstance(health, str) or health not in {"healthy", "degraded", "failed"}:
            return False
        name = self._normalize_name(feature_name)
        if not name:
            return False
        registry = self._read()
        if name not in registry:
            return False
        registry[name]["health"] = health
        if health == "failed":
            registry[name]["status"] = "FAILED"
            registry[name]["enabled"] = False
        self.store.write(registry)
        return True

    def register(self, feature_name: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        name = self._normalize_name(feature_name)
        if not name:
            raise ValueError("A non-empty feature name is required")
        if len(name) > self.MAX_EXTENSION_NAME_LENGTH:
            raise ValueError("Feature name exceeds the supported length")
        if not isinstance(metadata, dict):
            raise ValueError("Feature metadata must be an object")
        item = deepcopy(metadata)
        item.setdefault("version", "1.0")
        item.setdefault("category", "extension")
        item.setdefault("status", "AVAILABLE")
        item.setdefault("dependencies", [])
        item.setdefault("capabilities", [])
        item.setdefault("configuration", {})
        item.setdefault("permissions", [])
        item.setdefault("health", "healthy")
        item.setdefault("tests", False)

        if not isinstance(item["status"], str) or item["status"] not in FEATURE_STATES:
            raise ValueError("Feature status is invalid")
        if not isinstance(item["health"], str) or item["health"] not in {"healthy", "degraded", "failed"}:
            raise ValueError("Feature health is invalid")
        for key in ("dependencies", "capabilities", "permissions"):
            values = item[key]
            if (
                not isinstance(values, list)
                or len(values) > self.MAX_LIST_ITEMS
                or not all(
                    isinstance(value, str)
                    and value.strip()
                    and len(value) <= self.MAX_METADATA_TEXT_LENGTH
                    for value in values
                )
            ):
                raise ValueError(
                    f"Feature {key} must contain at most {self.MAX_LIST_ITEMS} bounded strings"
                )
        for key in ("version", "category"):
            if (
                not isinstance(item[key], str)
                or not item[key].strip()
                or len(item[key]) > self.MAX_METADATA_TEXT_LENGTH
            ):
                raise ValueError(f"Feature {key} is invalid")
        if not isinstance(item["configuration"], dict):
            raise ValueError("Feature configuration must be an object")
        if not isinstance(item["tests"], bool):
            raise ValueError("Feature tests must be a boolean")

        item["feature_id"] = name
        if item["health"] == "failed" and item["status"] == "ENABLED":
            item["status"] = "FAILED"
        item["enabled"] = item["status"] == "ENABLED"
        registry = self._read()
        if name in registry:
            raise ValueError("Feature already exists; registration cannot overwrite existing state")
        if len(registry) >= self.MAX_FEATURES:
            raise ValueError("Feature registry capacity reached")
        unknown_dependencies = [dependency for dependency in item["dependencies"] if dependency not in registry]
        if unknown_dependencies:
            raise ValueError(f"Unknown feature dependencies: {', '.join(unknown_dependencies)}")
        registry[name] = item
        self.store.write(registry)
        return item

    def unregister(self, feature_name: str) -> bool:
        name = self._normalize_name(feature_name)
        if not name:
            return False
        registry = self._read()
        if name not in registry or name in CORE_FEATURES:
            return False
        if any(name in item.get("dependencies", []) and item.get("enabled") for item in registry.values()):
            return False
        del registry[name]
        self.store.write(registry)
        return True
