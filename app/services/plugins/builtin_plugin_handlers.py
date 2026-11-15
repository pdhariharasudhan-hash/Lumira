"""Application-owned, read-only handlers for the Lumira core plugin.

The handlers are bound only after the owner registers and approves the exact
``lumira.core`` manifest. No plugin-provided code is imported or executed.
"""
from __future__ import annotations

import asyncio
from typing import Any


CORE_PLUGIN_ID = "lumira.core"


def _artifact_list_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            "artifact_type": {"type": "string", "maxLength": 32},
            "include_archived": {"type": "boolean"},
        },
        "required": [],
        "additionalProperties": False,
    }


BUILTIN_HANDLERS = {
    "core.health_snapshot": {
        "permission": "device.read",
        "tool_manifest": {
            "description": "Read a bounded health snapshot of Lumira core subsystems.",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            "requires_approval": False,
        },
    },
    "core.memory_summary": {
        "permission": "memory.read",
        "tool_manifest": {
            "description": "Return counts of active cognitive memory records without exposing record contents.",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            "requires_approval": False,
        },
    },
    "core.memory_search": {
        "permission": "memory.read",
        "tool_manifest": {
            "description": "Search bounded cognitive memory using deterministic local ranking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 500},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            "requires_approval": False,
        },
    },
    "core.artifact_list": {
        "permission": "filesystem.artifacts.read",
        "tool_manifest": {
            "description": "List bounded artifact metadata without exposing storage paths or contents.",
            "parameters": _artifact_list_schema(),
            "requires_approval": False,
        },
    },
}


async def _health_snapshot(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.system.system_health_service import SystemHealthService

    return await asyncio.to_thread(SystemHealthService().snapshot)


async def _memory_summary(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.memory.memory_service import MemoryService

    summary = await asyncio.to_thread(MemoryService().summarize)
    return {"success": True, "summary": summary}


async def _memory_search(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.memory.memory_service import MemoryService

    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)
    result = await asyncio.to_thread(MemoryService().search, query, None, None, limit)
    return {"success": True, "query": query, "collections": result}


async def _artifact_list(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    def read_records() -> list[dict[str, Any]]:
        records = ArtifactManagerService().get_all_artifacts()
        if not isinstance(records, list):
            raise ValueError("artifact_index_invalid")
        artifact_type = arguments.get("artifact_type")
        include_archived = arguments.get("include_archived", False)
        limit = arguments.get("limit", 20)
        visible = []
        for record in records:
            if not isinstance(record, dict):
                continue
            if not include_archived and record.get("archived") is True:
                continue
            if artifact_type and record.get("type") != artifact_type:
                continue
            # Deliberately omit filesystem paths, file names and content.
            visible.append({
                key: record.get(key)
                for key in ("artifact_id", "type", "source", "timestamp", "archived", "content_bytes")
                if key in record
            })
            if len(visible) >= limit:
                break
        return visible

    records = await asyncio.to_thread(read_records)
    return {"success": True, "count": len(records), "artifacts": records}


def bind_approved_builtin_handlers(runtime) -> dict[str, Any]:
    """Bind known app-owned handlers only when exact owner grants are present."""
    try:
        record = runtime.registry.get(CORE_PLUGIN_ID)
    except Exception:
        return {"success": False, "code": "plugin_registry_unavailable", "registered": 0}
    if not isinstance(record, dict) or record.get("approval_state") != "approved":
        return {"success": True, "registered": 0, "state": "not_approved"}

    manifest = record.get("manifest")
    grants = record.get("granted_permissions")
    if not isinstance(manifest, dict) or not isinstance(grants, list):
        return {"success": False, "code": "plugin_manifest_invalid", "registered": 0}
    capabilities = manifest.get("capabilities")
    declared = manifest.get("permissions")
    if not isinstance(capabilities, list) or not isinstance(declared, list):
        return {"success": False, "code": "plugin_manifest_invalid", "registered": 0}

    existing = {
        item.get("capability") for item in runtime.list_handlers()
        if item.get("plugin_id") == CORE_PLUGIN_ID
    }
    handlers = {
        "core.health_snapshot": _health_snapshot,
        "core.memory_summary": _memory_summary,
        "core.memory_search": _memory_search,
        "core.artifact_list": _artifact_list,
    }
    registered = 0
    skipped = []
    for capability, specification in BUILTIN_HANDLERS.items():
        if capability not in capabilities:
            continue
        permission = specification["permission"]
        if permission not in declared or permission not in grants:
            skipped.append({"capability": capability, "code": "permission_not_granted"})
            continue
        if capability in existing:
            continue
        try:
            runtime.register_handler(
                CORE_PLUGIN_ID,
                capability,
                specification["tool_manifest"],
                handlers[capability],
                required_permissions=[permission],
            )
            registered += 1
        except ValueError as exc:
            # Duplicate registration is benign only if reconciliation already
            # observed the existing handler; other errors remain visible.
            skipped.append({"capability": capability, "code": str(exc)[:120]})
        except Exception as exc:
            skipped.append({"capability": capability, "code": type(exc).__name__})
    return {"success": not skipped, "registered": registered, "skipped": skipped}
