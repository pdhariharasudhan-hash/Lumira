import json

import pytest

from app.services.plugins.plugin_registry import (
    PluginManifestError,
    PluginRegistry,
)


def _manifest(**overrides):
    value = {
        "schema_version": 1,
        "plugin_id": "notes.exporter",
        "name": "Notes Exporter",
        "version": "1.2.3",
        "api_version": "1",
        "description": "Exports selected notes.",
        "capabilities": ["notes.export"],
        "permissions": ["memory.read", "filesystem.artifacts.write"],
        "dependencies": [],
    }
    value.update(overrides)
    return value


def test_manifest_validation_normalizes_and_rejects_unknown_permissions():
    parsed = PluginRegistry.validate_manifest(_manifest())

    assert parsed.plugin_id == "notes.exporter"
    assert parsed.capabilities == ("notes.export",)
    assert parsed.permissions == ("memory.read", "filesystem.artifacts.write")

    with pytest.raises(PluginManifestError, match="permission"):
        PluginRegistry.validate_manifest(_manifest(permissions=["process.execute"]))


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": 2},
        {"plugin_id": "../escape"},
        {"version": "latest"},
        {"api_version": "99"},
        {"capabilities": ["*" ]},
        {"permissions": "memory.read"},
        {"extra": "not part of the schema"},
    ],
)
def test_manifest_rejects_unsafe_or_unsupported_fields(overrides):
    with pytest.raises(PluginManifestError):
        PluginRegistry.validate_manifest(_manifest(**overrides))


def test_register_requires_explicit_permission_approval_before_capability_is_active(tmp_path):
    registry = PluginRegistry(tmp_path / "plugins.json")
    registry.register(_manifest())

    assert registry.get("notes.exporter")["approval_state"] == "pending"
    assert registry.approved_capabilities() == {}
    assert registry.is_permission_granted("notes.exporter", "memory.read") is False

    with pytest.raises(ValueError, match="not declared"):
        registry.approve("notes.exporter", ["process.execute"])

    approved = registry.approve("notes.exporter", ["memory.read"])
    assert approved["approval_state"] == "pending"
    assert registry.approved_capabilities() == {}

    enabled = registry.approve(
        "notes.exporter",
        ["memory.read", "filesystem.artifacts.write"],
    )
    assert enabled["approval_state"] == "approved"
    assert registry.approved_capabilities() == {"notes.export": ["notes.exporter"]}
    assert registry.is_permission_granted("notes.exporter", "memory.read") is True


def test_registry_persists_approval_and_disable_revokes_execution_readiness(tmp_path):
    path = tmp_path / "plugins.json"
    registry = PluginRegistry(path)
    registry.register(_manifest())
    registry.approve("notes.exporter", ["memory.read", "filesystem.artifacts.write"])

    reloaded = PluginRegistry(path)
    assert reloaded.get("notes.exporter")["approval_state"] == "approved"
    assert reloaded.approved_capabilities() == {"notes.export": ["notes.exporter"]}

    reloaded.disable("notes.exporter")
    assert reloaded.approved_capabilities() == {}
    assert reloaded.is_permission_granted("notes.exporter", "memory.read") is False


def test_corrupt_registry_is_not_reset(tmp_path):
    path = tmp_path / "plugins.json"
    path.write_text(json.dumps({"schema_version": 9, "plugins": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="schema"):
        PluginRegistry(path)

    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 9


def test_plugins_require_registered_and_approved_dependencies(tmp_path):
    registry = PluginRegistry(tmp_path / "plugins.json")
    dependency = _manifest(plugin_id="base.storage", capabilities=["storage.read"], permissions=[])
    dependent = _manifest(plugin_id="notes.exporter", dependencies=["base.storage"])

    with pytest.raises(ValueError, match="registered first"):
        registry.register(dependent)

    registry.register(dependency)
    registry.register(dependent)
    with pytest.raises(ValueError, match="approval first"):
        registry.approve("notes.exporter", ["memory.read", "filesystem.artifacts.write"])

    registry.approve("base.storage", [])
    registry.approve("notes.exporter", ["memory.read", "filesystem.artifacts.write"])
    assert set(registry.approved_capabilities()) == {"storage.read", "notes.export"}

    registry.disable("base.storage")
    assert registry.get("notes.exporter")["approval_state"] == "disabled"
    assert registry.approved_capabilities() == {}


def test_registration_never_imports_an_entrypoint():
    manifest = _manifest(entrypoint="os:system")
    with pytest.raises(PluginManifestError, match="unknown"):
        PluginRegistry.validate_manifest(manifest)
