"""Application-owned, read-only handlers for the Lumira core plugin.

The handlers are bound only after the owner registers and approves the exact
``lumira.core`` manifest. No plugin-provided code is imported or executed.
"""
from __future__ import annotations

import asyncio
from typing import Any


CORE_PLUGIN_ID = "lumira.core.system"


BUILTIN_PLUGIN_MANIFESTS = {
    "lumira.core.system": {
        "schema_version": 1, "plugin_id": "lumira.core.system",
        "name": "Lumira Core System Read", "version": "1.0.0", "api_version": "1",
        "description": "Read-only system health capability.",
        "capabilities": ["core.health_snapshot"],
        "permissions": ["device.read"], "dependencies": [],
    },
    "lumira.core.memory.read": {
        "schema_version": 1, "plugin_id": "lumira.core.memory.read",
        "name": "Lumira Core Memory Read", "version": "1.0.0", "api_version": "1",
        "description": "Read-only cognitive memory and goal discovery capabilities.",
        "capabilities": ["core.memory_summary", "core.memory_search", "core.goal_list"],
        "permissions": ["memory.read"], "dependencies": [],
    },
    "lumira.core.memory.write": {
        "schema_version": 1, "plugin_id": "lumira.core.memory.write",
        "name": "Lumira Core Memory Write", "version": "1.0.0", "api_version": "1",
        "description": "Owner-approved cognitive memory and goal mutation capabilities.",
        "capabilities": ["core.memory_record_experience", "core.memory_archive", "core.goal_create", "core.goal_decompose", "core.goal_update"],
        "permissions": ["memory.write"], "dependencies": [],
    },
    "lumira.core.projects.read": {
        "schema_version": 1, "plugin_id": "lumira.core.projects.read",
        "name": "Lumira Core Project Read", "version": "1.0.0", "api_version": "1",
        "description": "Read-only project discovery capability.",
        "capabilities": ["core.project_list"],
        "permissions": ["filesystem.project.read"], "dependencies": [],
    },
    "lumira.core.artifacts.read": {
        "schema_version": 1, "plugin_id": "lumira.core.artifacts.read",
        "name": "Lumira Core Artifact Read", "version": "1.0.0", "api_version": "1",
        "description": "Read-only artifact metadata and integrity capabilities.",
        "capabilities": ["core.artifact_list", "core.artifact_verify"],
        "permissions": ["filesystem.artifacts.read"], "dependencies": [],
    },
    "lumira.core.artifacts.write": {
        "schema_version": 1, "plugin_id": "lumira.core.artifacts.write",
        "name": "Lumira Core Artifact Write", "version": "1.0.0", "api_version": "1",
        "description": "Owner-approved artifact archive and restore capabilities.",
        "capabilities": ["core.artifact_archive", "core.artifact_restore"],
        "permissions": ["filesystem.artifacts.write"], "dependencies": [],
    },
}

BUILTIN_PLUGIN_MANIFEST = BUILTIN_PLUGIN_MANIFESTS[CORE_PLUGIN_ID]

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
    "core.goal_list": {
        "permission": "memory.read",
        "tool_manifest": {
            "description": "List bounded active goal metadata for Brain planning and progress tracking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "maxLength": 200},
                    "status": {"type": "string", "enum": ["active", "paused", "completed", "blocked", "cancelled", "in_progress"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": [],
                "additionalProperties": False,
            },
            "requires_approval": False,
        },
    },
    "core.goal_update": {
        "permission": "memory.write",
        "tool_manifest": {
            "description": "Update the status and progress of an existing goal after one-time owner approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal_id": {"type": "string", "minLength": 1, "maxLength": 128},
                    "status": {"type": "string", "enum": ["active", "paused", "completed", "blocked", "cancelled", "in_progress"]},
                    "progress": {"type": "number", "minimum": 0, "maximum": 100},
                    "blockers": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 500}, "maxItems": 20},
                },
                "required": ["goal_id", "status"],
                "additionalProperties": False,
            },
            "requires_approval": True,
        },
    },
    "core.goal_decompose": {
        "permission": "memory.write",
        "tool_manifest": {
            "description": "Decompose an existing goal into bounded child objectives after one-time owner approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal_id": {"type": "string", "minLength": 1, "maxLength": 128},
                    "objectives": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 500}, "minItems": 1, "maxItems": 20},
                },
                "required": ["goal_id", "objectives"],
                "additionalProperties": False,
            },
            "requires_approval": True,
        },
    },
    "core.goal_create": {
        "permission": "memory.write",
        "tool_manifest": {
            "description": "Create a durable personal goal after one-time owner approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 500},
                    "objective": {"type": "string", "maxLength": 2000},
                    "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
                },
                "required": ["title"],
                "additionalProperties": False,
            },
            "requires_approval": True,
        },
    },
    "core.memory_archive": {
        "permission": "memory.write",
        "tool_manifest": {
            "description": "Archive a cognitive memory record without permanently deleting it; requires one-time owner approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "enum": ["goals", "decisions", "experiences", "learning_records"]},
                    "record_id": {"type": "string", "minLength": 1, "maxLength": 128},
                    "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                },
                "required": ["collection", "record_id", "reason"],
                "additionalProperties": False,
            },
            "requires_approval": True,
        },
    },
    "core.memory_record_experience": {
        "permission": "memory.write",
        "tool_manifest": {
            "description": "Record a user-approved experience in cognitive memory; verification is never asserted by this handler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "experience_type": {"type": "string", "enum": ["success", "failure", "decision", "workflow"]},
                    "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "outcome": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "lessons": {"type": "array", "items": {"type": "string", "maxLength": 500}, "maxItems": 10},
                    "project_id": {"type": "string", "maxLength": 100},
                    "goal_id": {"type": "string", "maxLength": 128},
                },
                "required": ["experience_type", "summary", "outcome"],
                "additionalProperties": False,
            },
            "requires_approval": True,
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
    "core.project_list": {
        "permission": "filesystem.project.read",
        "tool_manifest": {
            "description": "List bounded project names and version counts without exposing file paths or source contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "maxLength": 200},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": [],
                "additionalProperties": False,
            },
            "requires_approval": False,
        },
    },
    "core.artifact_verify": {
        "permission": "filesystem.artifacts.read",
        "tool_manifest": {
            "description": "Verify an artifact file against its stored checksum without returning its content.",
            "parameters": {
                "type": "object",
                "properties": {"artifact_id": {"type": "string", "minLength": 1, "maxLength": 128}},
                "required": ["artifact_id"],
                "additionalProperties": False,
            },
            "requires_approval": False,
        },
    },
    "core.artifact_archive": {
        "permission": "filesystem.artifacts.write",
        "tool_manifest": {
            "description": "Archive an artifact without deleting its stored content; requires one-time owner approval.",
            "parameters": {
                "type": "object",
                "properties": {"artifact_id": {"type": "string", "minLength": 1, "maxLength": 128}},
                "required": ["artifact_id"],
                "additionalProperties": False,
            },
            "requires_approval": True,
        },
    },
    "core.artifact_restore": {
        "permission": "filesystem.artifacts.write",
        "tool_manifest": {
            "description": "Restore an archived artifact without changing its stored content; requires one-time owner approval.",
            "parameters": {
                "type": "object",
                "properties": {"artifact_id": {"type": "string", "minLength": 1, "maxLength": 128}},
                "required": ["artifact_id"],
                "additionalProperties": False,
            },
            "requires_approval": True,
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


async def _goal_list(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.memory.memory_service import MemoryService

    query = arguments.get("query", "").strip().casefold()
    status = arguments.get("status")
    limit = arguments.get("limit", 20)

    def read_goals() -> list[dict[str, Any]]:
        records = MemoryService().get_all().get("goals", [])
        if not isinstance(records, list):
            raise ValueError("goal_memory_invalid")
        visible = []
        for goal in records:
            if not isinstance(goal, dict) or goal.get("archived") is True:
                continue
            if status and goal.get("status") != status:
                continue
            searchable = f"{goal.get('title', '')} {goal.get('objective', '')}".casefold()
            if query and query not in searchable:
                continue
            visible.append({
                key: goal.get(key)
                for key in ("goal_id", "title", "objective", "priority", "status", "progress", "deadline", "project_id", "parent_goal_id")
                if key in goal
            })
            if len(visible) >= limit:
                break
        return visible

    goals = await asyncio.to_thread(read_goals)
    return {"success": True, "count": len(goals), "goals": goals}


async def _goal_update(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.memory.memory_service import MemoryService

    updates = {key: arguments[key] for key in ("status", "progress", "blockers") if key in arguments}
    if updates.get("status") == "completed" and "progress" not in updates:
        updates["progress"] = 100.0
    goal = await asyncio.to_thread(
        MemoryService().update_goal,
        arguments["goal_id"],
        **updates,
    )
    return {
        "success": True,
        "updated": True,
        "goal": {
            "goal_id": goal.get("goal_id"),
            "title": goal.get("title"),
            "status": goal.get("status"),
            "progress": goal.get("progress"),
        },
    }


async def _goal_decompose(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.memory.memory_service import MemoryService

    result = await asyncio.to_thread(
        MemoryService().decompose_goal,
        arguments["goal_id"],
        arguments["objectives"],
    )
    objectives = result.get("objectives", []) if isinstance(result, dict) else []
    return {
        "success": True,
        "created_count": len(objectives),
        "objectives": [
            {"goal_id": item.get("goal_id"), "title": item.get("title")}
            for item in objectives if isinstance(item, dict)
        ],
    }


async def _goal_create(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.memory.memory_service import MemoryService

    goal = await asyncio.to_thread(
        MemoryService().create_goal,
        arguments["title"],
        arguments.get("objective", ""),
        arguments.get("priority", "normal"),
    )
    return {
        "success": True,
        "created": True,
        "goal": {
            "goal_id": goal.get("goal_id"),
            "title": goal.get("title"),
            "priority": goal.get("priority"),
            "status": goal.get("status"),
        },
    }


async def _memory_archive(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.memory.memory_service import MemoryService

    record = await asyncio.to_thread(
        MemoryService().evolve,
        arguments["collection"],
        arguments["record_id"],
        forget=True,
        reason=arguments["reason"],
        source="lumira_core_plugin",
    )
    return {
        "success": True,
        "archived": record.get("archived") is True,
        "collection": arguments["collection"],
        "record_id": arguments["record_id"],
        "permanently_deleted": False,
    }


async def _memory_record_experience(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.memory.memory_service import MemoryService

    record = await asyncio.to_thread(
        MemoryService().record_experience,
        arguments["experience_type"],
        arguments["summary"],
        arguments["outcome"],
        arguments.get("project_id"),
        arguments.get("goal_id"),
        arguments.get("lessons", []),
        [],
        None,
        False,
    )
    return {"success": True, "recorded": True, "verified": False, "experience_id": record.get("experience_id")}


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


async def _project_list(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.projects.project_discovery_service import ProjectDiscoveryService

    query = arguments.get("query", "").strip().casefold()
    limit = arguments.get("limit", 20)

    def read_projects() -> list[dict[str, Any]]:
        projects = ProjectDiscoveryService().get_projects()
        visible = []
        for project in projects:
            name = project.get("project") if isinstance(project, dict) else None
            if not isinstance(name, str) or (query and query not in name.casefold()):
                continue
            visible.append({"project": name, "versions": project.get("versions", 0)})
            if len(visible) >= limit:
                break
        return visible

    projects = await asyncio.to_thread(read_projects)
    return {"success": True, "count": len(projects), "projects": projects}


async def _artifact_verify(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    result = await asyncio.to_thread(
        ArtifactManagerService().verify_artifact_content, arguments["artifact_id"]
    )
    return result


async def _artifact_archive(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    archived = await asyncio.to_thread(
        ArtifactManagerService().archive_artifact, arguments["artifact_id"]
    )
    return {
        "success": archived is True,
        "archived": archived is True,
        "artifact_id": arguments["artifact_id"],
        "code": None if archived else "artifact_not_found",
    }


async def _artifact_restore(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services.artifacts.artifact_manager_service import ArtifactManagerService

    restored = await asyncio.to_thread(
        ArtifactManagerService().restore_artifact, arguments["artifact_id"]
    )
    return {
        "success": restored is True,
        "restored": restored is True,
        "artifact_id": arguments["artifact_id"],
        "code": None if restored else "artifact_not_found",
    }


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
    """Bind app-owned handlers only for individually approved permission scopes."""
    handlers = {
        "core.health_snapshot": _health_snapshot,
        "core.memory_summary": _memory_summary,
        "core.memory_search": _memory_search,
        "core.memory_record_experience": _memory_record_experience,
        "core.memory_archive": _memory_archive,
        "core.goal_create": _goal_create,
        "core.goal_decompose": _goal_decompose,
        "core.goal_update": _goal_update,
        "core.goal_list": _goal_list,
        "core.project_list": _project_list,
        "core.artifact_list": _artifact_list,
        "core.artifact_archive": _artifact_archive,
        "core.artifact_verify": _artifact_verify,
        "core.artifact_restore": _artifact_restore,
    }
    registered = 0
    skipped = []
    pending = []
    try:
        existing_handlers = runtime.list_handlers()
    except Exception:
        return {"success": False, "code": "plugin_registry_unavailable", "registered": 0}

    for plugin_id, expected_manifest in BUILTIN_PLUGIN_MANIFESTS.items():
        try:
            record = runtime.registry.get(plugin_id)
        except Exception:
            return {"success": False, "code": "plugin_registry_unavailable", "registered": registered}
        if not isinstance(record, dict):
            pending.append(plugin_id)
            continue
        if record.get("manifest") != expected_manifest:
            skipped.append({"plugin_id": plugin_id, "code": "builtin_manifest_mismatch"})
            continue
        if record.get("approval_state") != "approved":
            pending.append(plugin_id)
            continue
        grants = record.get("granted_permissions")
        if not isinstance(grants, list):
            skipped.append({"plugin_id": plugin_id, "code": "plugin_grants_invalid"})
            continue
        existing = {
            item.get("capability") for item in existing_handlers
            if item.get("plugin_id") == plugin_id
        }
        for capability in expected_manifest["capabilities"]:
            specification = BUILTIN_HANDLERS[capability]
            permission = specification["permission"]
            if permission not in expected_manifest["permissions"] or permission not in grants:
                skipped.append({"plugin_id": plugin_id, "capability": capability, "code": "permission_not_granted"})
                continue
            if capability in existing:
                continue
            try:
                runtime.register_handler(
                    plugin_id, capability, specification["tool_manifest"],
                    handlers[capability], required_permissions=[permission],
                )
                registered += 1
            except Exception as exc:
                skipped.append({"plugin_id": plugin_id, "capability": capability, "code": type(exc).__name__})
    return {
        "success": not skipped,
        "registered": registered,
        "pending_approval": pending,
        "skipped": skipped,
    }
