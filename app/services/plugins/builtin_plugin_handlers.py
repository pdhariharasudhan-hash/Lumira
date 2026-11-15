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
        "core.memory_record_experience": _memory_record_experience,
        "core.goal_create": _goal_create,
        "core.goal_decompose": _goal_decompose,
        "core.goal_update": _goal_update,
        "core.goal_list": _goal_list,
        "core.project_list": _project_list,
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
