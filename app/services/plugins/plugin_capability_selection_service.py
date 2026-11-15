"""Deterministic, conservative routing for explicit read-only user requests.

Only exact natural-language request patterns may select tools. The selector
never chooses write or approval-required handlers and never invents arguments.
"""
from __future__ import annotations
import re
from typing import Any

_READ_ONLY_PERMISSIONS = {"device.read", "memory.read", "filesystem.project.read", "filesystem.artifacts.read"}

# Phrase lists are intentionally narrow. Ambiguous or unmatched requests stay
# on the normal conversation path; no model-generated tool arguments are used.
_RULES = (
    (("system health", "health check", "health snapshot", "lumira health", "system status", "check lumira health"), "lumira.core.system", "core.health_snapshot"),
    (("provider status", "provider list", "which providers", "show providers", "list providers"), "lumira.core.system", "core.provider_status"),
    (("model status", "model list", "which models", "show models", "list models"), "lumira.core.system", "core.model_status"),
    (("memory summary", "memory counts", "summarize memory", "how much memory is stored"), "lumira.core.memory.read", "core.memory_summary"),
    (("list goals", "show goals", "my goals", "goal list"), "lumira.core.memory.read", "core.goal_list"),
    (("list tasks", "show tasks", "my tasks", "list todos", "show todos", "todo list"), "lumira.core.memory.read", "core.todo_list"),
    (("list notes", "show notes", "my notes", "note list"), "lumira.core.memory.read", "core.note_list"),
    (("list projects", "show projects", "my projects", "project list"), "lumira.core.projects.read", "core.project_list"),
    (("list artifacts", "show artifacts", "my artifacts", "artifact list"), "lumira.core.artifacts.read", "core.artifact_list"),
)

def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text) is not None

class PluginCapabilitySelectionService:
    """Select a single explicitly requested, non-mutating built-in capability."""
    def select(self, message: str, handlers: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not isinstance(message, str) or not message.strip() or not isinstance(handlers, list):
            return None
        text = " ".join(message.casefold().split())
        matches = []
        for phrases, plugin_id, capability in _RULES:
            if any(_contains_phrase(text, phrase) for phrase in phrases):
                matches.append((plugin_id, capability))
        if len(set(matches)) != 1:
            return None
        plugin_id, capability = matches[0]
        handler = next((item for item in handlers if isinstance(item, dict) and item.get("plugin_id") == plugin_id and item.get("capability") == capability), None)
        if handler is None:
            return None
        manifest = handler.get("tool_manifest")
        permissions = handler.get("required_permissions")
        if not isinstance(manifest, dict) or manifest.get("requires_approval") is not False:
            return None
        if not isinstance(permissions, list) or not set(permissions).issubset(_READ_ONLY_PERMISSIONS):
            return None
        parameters = manifest.get("parameters")
        if not isinstance(parameters, dict) or parameters.get("type") != "object" or parameters.get("additionalProperties") is not False:
            return None
        required = parameters.get("required", [])
        if not isinstance(required, list) or required:
            return None
        return {"plugin_id": plugin_id, "capability": capability, "arguments": {}}
