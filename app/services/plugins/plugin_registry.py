"""Validate plugin declarations and persist explicit permission approvals.

This module deliberately does not load or execute plugin code. A plugin record
is metadata only; an approved capability means that its manifest and declared
permissions passed local validation, not that a runtime is available or safe.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from app.services.persistence.atomic_json_store import (
    AtomicJsonStore,
    PersistenceIntegrityError,
)


PLUGIN_REGISTRY_SCHEMA_VERSION = 1
SUPPORTED_PLUGIN_API_VERSION = "1"

# Deliberately omit process execution, shell access, arbitrary filesystem
# access, credential access, and unrestricted networking. New permissions
# require a reviewed code change before a manifest can request them.
PLUGIN_PERMISSION_ALLOWLIST = frozenset(
    {
        "memory.read",
        "memory.write",
        "filesystem.project.read",
        "filesystem.project.write",
        "filesystem.artifacts.read",
        "filesystem.artifacts.write",
        "network.public_https",
        "microphone",
        "audio.output",
        "device.read",
    }
)

_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)*$")
_PACKAGE_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "plugin_id",
        "name",
        "version",
        "api_version",
        "description",
        "capabilities",
        "permissions",
        "dependencies",
    }
)
_RECORD_KEYS = frozenset({"manifest", "approval_state", "granted_permissions"})
_APPROVAL_STATES = frozenset({"pending", "approved", "disabled"})


class PluginManifestError(ValueError):
    """Raised when a plugin declaration is malformed or requests unsafe access."""


class PluginRegistryError(PersistenceIntegrityError):
    """Raised when the persisted plugin registry cannot be trusted."""


@dataclass(frozen=True)
class PluginManifest:
    schema_version: int
    plugin_id: str
    name: str
    version: str
    api_version: str
    description: str
    capabilities: tuple[str, ...]
    permissions: tuple[str, ...]
    dependencies: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible representation."""
        result = asdict(self)
        for key in ("capabilities", "permissions", "dependencies"):
            result[key] = list(result[key])
        return result


class PluginRegistry:
    """A persistent manifest/consent registry; it is not a plugin executor."""

    MAX_PLUGINS = 100
    MAX_MANIFEST_BYTES = 16_384
    MAX_CAPABILITIES = 32
    MAX_PERMISSIONS = 32
    MAX_DEPENDENCIES = 20
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 512

    def __init__(self, registry_path: str | Path = "memory/plugins/registry.json"):
        self.registry_path = Path(registry_path)
        self.store = AtomicJsonStore(self.registry_path)
        self.store.read_or_create(self._default_document())
        self._read_document()

    @classmethod
    def validate_manifest(cls, value: Mapping[str, Any] | PluginManifest) -> PluginManifest:
        """Validate a manifest without loading any declared module or package."""
        if isinstance(value, PluginManifest):
            value = value.to_dict()
        if not isinstance(value, Mapping):
            raise PluginManifestError("manifest must be an object")

        try:
            encoded_size = len(
                json.dumps(dict(value), ensure_ascii=False, allow_nan=False).encode("utf-8")
            )
        except (TypeError, ValueError, RecursionError) as exc:
            raise PluginManifestError("manifest is not a bounded mapping") from exc
        if encoded_size > cls.MAX_MANIFEST_BYTES:
            raise PluginManifestError("manifest exceeds the size limit")

        keys = set(value.keys())
        missing = _MANIFEST_KEYS - keys
        unknown = keys - _MANIFEST_KEYS
        if missing:
            raise PluginManifestError(f"manifest is missing fields: {', '.join(sorted(missing))}")
        if unknown:
            raise PluginManifestError(f"manifest has unknown fields: {', '.join(sorted(map(str, unknown)))}")

        schema_version = value.get("schema_version")
        if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
            raise PluginManifestError("unsupported manifest schema version")

        plugin_id = value.get("plugin_id")
        if not isinstance(plugin_id, str) or len(plugin_id) > 96 or not _PLUGIN_ID.fullmatch(plugin_id):
            raise PluginManifestError("plugin_id is invalid")

        name = cls._bounded_text(value.get("name"), "name", cls.MAX_NAME_LENGTH)
        description = cls._bounded_text(
            value.get("description"), "description", cls.MAX_DESCRIPTION_LENGTH, allow_empty=True
        )

        version = value.get("version")
        if not isinstance(version, str) or not _PACKAGE_VERSION.fullmatch(version):
            raise PluginManifestError("version must be a semantic version")

        api_version = value.get("api_version")
        if not isinstance(api_version, str) or api_version != SUPPORTED_PLUGIN_API_VERSION:
            raise PluginManifestError("unsupported plugin API version")

        capabilities = cls._string_list(value.get("capabilities"), "capabilities", cls.MAX_CAPABILITIES)
        for capability in capabilities:
            if not _CAPABILITY.fullmatch(capability):
                raise PluginManifestError(f"invalid capability: {capability}")

        permissions = cls._string_list(value.get("permissions"), "permissions", cls.MAX_PERMISSIONS)
        unknown_permissions = sorted(set(permissions) - PLUGIN_PERMISSION_ALLOWLIST)
        if unknown_permissions:
            raise PluginManifestError(
                f"permission is not allowed: {', '.join(unknown_permissions)}"
            )

        dependencies = cls._string_list(value.get("dependencies"), "dependencies", cls.MAX_DEPENDENCIES)
        for dependency in dependencies:
            if not _PLUGIN_ID.fullmatch(dependency):
                raise PluginManifestError(f"invalid dependency plugin_id: {dependency}")
            if dependency == plugin_id:
                raise PluginManifestError("plugin cannot depend on itself")

        return PluginManifest(
            schema_version=1,
            plugin_id=plugin_id,
            name=name,
            version=version,
            api_version=api_version,
            description=description,
            capabilities=tuple(capabilities),
            permissions=tuple(permissions),
            dependencies=tuple(dependencies),
        )

    @staticmethod
    def _bounded_text(value: Any, field: str, max_length: int, allow_empty: bool = False) -> str:
        if not isinstance(value, str):
            raise PluginManifestError(f"{field} must be text")
        normalized = value.strip()
        if (not normalized and not allow_empty) or len(normalized) > max_length:
            raise PluginManifestError(f"{field} length is invalid")
        return normalized

    @staticmethod
    def _string_list(value: Any, field: str, max_items: int) -> list[str]:
        if not isinstance(value, list) or len(value) > max_items:
            raise PluginManifestError(f"{field} must be a list with at most {max_items} items")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip() or len(item) > 128:
                raise PluginManifestError(f"{field} contains an invalid value")
            item = item.strip()
            if item in normalized:
                raise PluginManifestError(f"{field} contains a duplicate value")
            normalized.append(item)
        return normalized

    @staticmethod
    def _default_document() -> dict[str, Any]:
        return {"schema_version": PLUGIN_REGISTRY_SCHEMA_VERSION, "plugins": {}}

    def _read_document(self) -> dict[str, Any]:
        document = self.store.read(default=None)
        self._validate_document(document)
        return document

    @classmethod
    def _validate_document(cls, document: Any) -> None:
        if not isinstance(document, dict):
            raise PluginRegistryError("plugin registry must be an object")
        if set(document) != {"schema_version", "plugins"}:
            raise PluginRegistryError("plugin registry fields are invalid")
        version = document.get("schema_version")
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version != PLUGIN_REGISTRY_SCHEMA_VERSION
        ):
            raise PluginRegistryError("unsupported plugin registry schema version")
        plugins = document.get("plugins")
        if not isinstance(plugins, dict) or len(plugins) > cls.MAX_PLUGINS:
            raise PluginRegistryError("plugin registry entries are invalid")

        manifests: dict[str, PluginManifest] = {}
        for plugin_id, record in plugins.items():
            if not isinstance(plugin_id, str) or not isinstance(record, dict) or set(record) != _RECORD_KEYS:
                raise PluginRegistryError("plugin registry record is malformed")
            try:
                manifest = cls.validate_manifest(record.get("manifest"))
            except PluginManifestError as exc:
                raise PluginRegistryError("plugin registry contains an invalid manifest") from exc
            if manifest.plugin_id != plugin_id:
                raise PluginRegistryError("plugin registry key does not match manifest id")
            manifests[plugin_id] = manifest
            state = record.get("approval_state")
            if not isinstance(state, str) or state not in _APPROVAL_STATES:
                raise PluginRegistryError("plugin approval state is invalid")
            grants = record.get("granted_permissions")
            if (
                not isinstance(grants, list)
                or any(not isinstance(item, str) for item in grants)
                or len(grants) != len(set(grants))
                or not set(grants).issubset(manifest.permissions)
            ):
                raise PluginRegistryError("plugin permission grants are invalid")
            if state == "approved" and not set(manifest.permissions).issubset(grants):
                raise PluginRegistryError("approved plugin is missing required permission grants")

        for plugin_id, manifest in manifests.items():
            missing = sorted(set(manifest.dependencies) - set(manifests))
            if missing:
                raise PluginRegistryError(
                    f"plugin {plugin_id} has unregistered dependencies: {', '.join(missing)}"
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(plugin_id: str) -> None:
            if plugin_id in visiting:
                raise PluginRegistryError("plugin dependency cycle detected")
            if plugin_id in visited:
                return
            visiting.add(plugin_id)
            for dependency in manifests[plugin_id].dependencies:
                visit(dependency)
            visiting.remove(plugin_id)
            visited.add(plugin_id)

        for plugin_id in manifests:
            visit(plugin_id)

        for plugin_id, manifest in manifests.items():
            if document["plugins"][plugin_id]["approval_state"] == "approved":
                unapproved = [
                    dependency
                    for dependency in manifest.dependencies
                    if document["plugins"][dependency]["approval_state"] != "approved"
                ]
                if unapproved:
                    raise PluginRegistryError(
                        f"approved plugin {plugin_id} has unapproved dependencies"
                    )

    def _update(self, mutate: Callable[[dict[str, Any]], Any]) -> Any:
        result: dict[str, Any] = {}

        def apply(document: Any) -> None:
            self._validate_document(document)
            result["value"] = mutate(document)
            self._validate_document(document)

        self.store.update(apply, default=None)
        return deepcopy(result.get("value"))

    @staticmethod
    def _require_plugin(plugins: dict[str, Any], plugin_id: str) -> dict[str, Any]:
        if not isinstance(plugin_id, str) or plugin_id not in plugins:
            raise KeyError(f"plugin not found: {plugin_id}")
        return plugins[plugin_id]

    def register(self, manifest: Mapping[str, Any] | PluginManifest) -> dict[str, Any]:
        parsed = self.validate_manifest(manifest)
        record = {
            "manifest": parsed.to_dict(),
            "approval_state": "pending",
            "granted_permissions": [],
        }

        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            plugins = document["plugins"]
            if parsed.plugin_id in plugins:
                raise ValueError("plugin already registered; replacement requires explicit removal")
            if len(plugins) >= self.MAX_PLUGINS:
                raise ValueError("plugin registry capacity reached")
            missing = sorted(set(parsed.dependencies) - set(plugins))
            if missing:
                raise ValueError(f"plugin dependencies must be registered first: {', '.join(missing)}")
            plugins[parsed.plugin_id] = deepcopy(record)
            return record

        return self._update(mutate)

    def get(self, plugin_id: str) -> dict[str, Any] | None:
        document = self._read_document()
        record = document["plugins"].get(plugin_id)
        return deepcopy(record) if record is not None else None

    def list_plugins(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._read_document()["plugins"])

    def approve(self, plugin_id: str, granted_permissions: list[str] | tuple[str, ...]) -> dict[str, Any]:
        requested = self._string_list(list(granted_permissions) if isinstance(granted_permissions, tuple) else granted_permissions,
                                      "granted_permissions", self.MAX_PERMISSIONS)

        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            record = self._require_plugin(document["plugins"], plugin_id)
            manifest = self.validate_manifest(record["manifest"])
            undeclared = sorted(set(requested) - set(manifest.permissions))
            if undeclared:
                raise ValueError(f"permission was not declared: {', '.join(undeclared)}")
            unapproved_dependencies = [
                dependency
                for dependency in manifest.dependencies
                if document["plugins"][dependency]["approval_state"] != "approved"
            ]
            if unapproved_dependencies:
                raise ValueError(
                    "plugin dependencies require approval first: "
                    + ", ".join(unapproved_dependencies)
                )
            record["granted_permissions"] = requested
            record["approval_state"] = (
                "approved"
                if set(manifest.permissions).issubset(requested)
                else "pending"
            )
            return record

        return self._update(mutate)

    def revoke(self, plugin_id: str, permission: str) -> dict[str, Any]:
        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            record = self._require_plugin(document["plugins"], plugin_id)
            manifest = self.validate_manifest(record["manifest"])
            if permission not in manifest.permissions:
                raise ValueError("permission was not declared")
            grants = record["granted_permissions"]
            if permission in grants:
                grants.remove(permission)
            record["approval_state"] = (
                "approved"
                if set(manifest.permissions).issubset(grants)
                else "pending"
            )
            self._disable_approved_dependents(document["plugins"], plugin_id)
            return record

        return self._update(mutate)

    def disable(self, plugin_id: str) -> dict[str, Any]:
        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            record = self._require_plugin(document["plugins"], plugin_id)
            record["approval_state"] = "disabled"
            self._disable_approved_dependents(document["plugins"], plugin_id)
            return record

        return self._update(mutate)

    def approved_capabilities(self) -> dict[str, list[str]]:
        """Return discovery metadata for fully approved manifests, never execute them."""
        result: dict[str, list[str]] = {}
        for plugin_id, record in self._read_document()["plugins"].items():
            if record["approval_state"] != "approved":
                continue
            manifest = self.validate_manifest(record["manifest"])
            for capability in manifest.capabilities:
                result.setdefault(capability, []).append(plugin_id)
        return {key: sorted(value) for key, value in sorted(result.items())}

    def is_permission_granted(self, plugin_id: str, permission: str) -> bool:
        if not isinstance(plugin_id, str) or not isinstance(permission, str):
            return False
        record = self._read_document()["plugins"].get(plugin_id)
        return bool(
            record
            and record["approval_state"] == "approved"
            and permission in record["granted_permissions"]
        )

    @staticmethod
    def _disable_approved_dependents(plugins: dict[str, Any], plugin_id: str) -> None:
        """Fail closed for approved plugins whose dependency just lost approval."""
        unavailable = {plugin_id}
        changed = True
        while changed:
            changed = False
            for dependent_id, record in plugins.items():
                if record["approval_state"] != "approved":
                    continue
                manifest = PluginRegistry.validate_manifest(record["manifest"])
                if unavailable.intersection(manifest.dependencies):
                    record["approval_state"] = "disabled"
                    unavailable.add(dependent_id)
                    changed = True
