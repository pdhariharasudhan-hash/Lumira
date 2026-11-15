"""Metadata and consent primitives for the disabled-by-default plugin system."""

from app.services.plugins.plugin_registry import (
    PluginManifest,
    PluginManifestError,
    PluginRegistry,
    PluginRegistryError,
)

__all__ = [
    "PluginManifest",
    "PluginManifestError",
    "PluginRegistry",
    "PluginRegistryError",
]
