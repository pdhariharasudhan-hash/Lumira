from copy import deepcopy
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.sessions.session_manager_service import SessionManagerService, redact_sensitive_value
from app.services.work_items.work_item_service import WorkItemService

router = APIRouter()

def _int_param(value, default, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(minimum, min(maximum, value))


def _parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _sessions(limit: int = 200):
    try:
        return SessionManagerService().list_sessions(limit)
    except PersistenceIntegrityError as exc:
        raise HTTPException(status_code=503, detail="Session data is unavailable or invalid") from exc


@router.get("/sessions/summary")
def session_summary():
    sessions = _sessions(200)
    counts = {"active": 0, "paused": 0, "closed": 0}
    projects, modes, workspaces = {}, {}, {}
    stale, empty_context, recoverable = [], [], []
    cutoff = datetime.now(UTC) - timedelta(days=7)
    for session in sessions:
        status = session.get("status")
        if status in counts:
            counts[status] += 1
        for target, value in ((projects, session.get("project_id") or "(unassigned)"),
                              (modes, session.get("active_mode") or "auto"),
                              (workspaces, session.get("workspace_id") or "(unknown)")):
            target[value] = target.get(value, 0) + 1
        updated = _parse_time(session.get("updated_at"))
        if status != "closed" and updated and updated < cutoff:
            stale.append(session.get("session_id"))
        if not session.get("recent_messages") and not session.get("current_goal") and not session.get("project_id"):
            empty_context.append(session.get("session_id"))
        if status in {"active", "paused"} and session.get("context_snapshots"):
            recoverable.append(session.get("session_id"))
    return {
        "success": True, "generated_at": datetime.now(UTC).isoformat(),
        "scanned_sessions": len(sessions), "truncated": len(sessions) >= 200,
        "status_counts": counts, "project_distribution": dict(sorted(projects.items(), key=lambda x: (-x[1], x[0]))[:50]),
        "mode_distribution": dict(sorted(modes.items(), key=lambda x: (-x[1], x[0]))[:30]),
        "workspace_distribution": dict(sorted(workspaces.items(), key=lambda x: (-x[1], x[0]))[:50]),
        "stale_session_ids": stale[:100], "sessions_without_context_ids": empty_context[:100],
        "sessions_with_recovery_snapshots": recoverable[:100],
    }


@router.get("/sessions/search")
def search_sessions(
    q: str = Query(min_length=1, max_length=200),
    status: str | None = Query(default=None, pattern="^(active|paused|closed)$"),
    project_id: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=30, ge=1, le=100),
):
    limit = _int_param(limit, 30, 1, 100)
    status = status if isinstance(status, str) else None
    project_id = project_id if isinstance(project_id, str) else None
    query = q.strip().casefold()
    if not query:
        raise HTTPException(status_code=422, detail="search query must not be empty")
    matches = []
    for session in _sessions(200):
        if status and session.get("status") != status:
            continue
        if project_id is not None and session.get("project_id") != project_id:
            continue
        conversation = session.get("conversation") if isinstance(session.get("conversation"), dict) else {}
        fields = [session.get(key) for key in ("session_id", "workspace_id", "project_id", "active_project", "active_version", "active_mode", "current_goal", "goal_id", "last_command")]
        fields.extend(conversation.get(key) for key in ("summary", "current_topic", "active_objective", "language_context"))
        # Message bodies are searchable for discovery, but are never returned in
        # search results; this preserves useful recall without exposing content.
        recent_messages = session.get("recent_messages", [])
        if isinstance(recent_messages, list):
            fields.extend(
                message.get(key)
                for message in recent_messages[-20:]
                if isinstance(message, dict)
                for key in ("content", "text")
            )
        if query in " ".join(str(value or "") for value in fields).casefold():
            matches.append({
                "session_id": session.get("session_id"), "status": session.get("status"),
                "workspace_id": session.get("workspace_id"), "project_id": session.get("project_id"),
                "active_project": session.get("active_project"), "active_mode": session.get("active_mode"),
                "current_goal": session.get("current_goal"), "updated_at": session.get("updated_at"),
                "recent_message_count": len(session.get("recent_messages", [])) if isinstance(session.get("recent_messages"), list) else 0,
            })
    matches.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("session_id") or "")), reverse=True)
    return {"success": True, "query": q.strip(), "total": len(matches), "sessions": matches[:limit]}


@router.get("/sessions/export")
def export_sessions(
    status: str | None = Query(default=None, pattern="^(active|paused|closed)$"),
    project_id: str | None = Query(default=None, max_length=100),
    include_recent_messages: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
):
    limit = _int_param(limit, 50, 1, 100)
    status = status if isinstance(status, str) else None
    project_id = project_id if isinstance(project_id, str) else None
    sessions = _sessions(200)
    if status:
        sessions = [item for item in sessions if item.get("status") == status]
    if project_id is not None:
        sessions = [item for item in sessions if item.get("project_id") == project_id]
    sessions.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("session_id") or "")))
    exported = []
    for session in sessions[:limit]:
        record = {key: deepcopy(session.get(key)) for key in (
            "session_id", "conversation_id", "created_at", "updated_at", "status", "workspace_id",
            "project_id", "active_project", "active_version", "active_mode", "current_goal", "goal_id",
            "conversation", "context_snapshots",
        )}
        if include_recent_messages:
            record["recent_messages"] = deepcopy(session.get("recent_messages", [])[-10:])
        exported.append(redact_sensitive_value(record))
    return {"success": True, "schema_version": 1, "exported_at": datetime.now(UTC).isoformat(),
            "count": len(exported), "truncated": len(sessions) > limit, "sessions": exported}


@router.get("/sessions/{session_id}/health")
def session_health(session_id: str):
    try:
        session = SessionManagerService().get_session(session_id)
    except PersistenceIntegrityError as exc:
        raise HTTPException(status_code=503, detail="Session data is unavailable or invalid") from exc
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    now = datetime.now(UTC)
    updated = _parse_time(session.get("updated_at"))
    messages = session.get("recent_messages", []) if isinstance(session.get("recent_messages"), list) else []
    snapshots = session.get("context_snapshots", []) if isinstance(session.get("context_snapshots"), list) else []
    conversation = session.get("conversation") if isinstance(session.get("conversation"), dict) else {}
    age_minutes = round((now - updated).total_seconds() / 60, 2) if updated else None
    return {
        "success": True, "session_id": session_id, "status": session.get("status"),
        "created_at": session.get("created_at"), "updated_at": session.get("updated_at"),
        "age_since_update_minutes": age_minutes,
        "is_stale": bool(updated and updated < now - timedelta(days=7) and session.get("status") != "closed"),
        "context": {
            "workspace_id": session.get("workspace_id"), "project_id": session.get("project_id"),
            "active_project": session.get("active_project"), "active_version": session.get("active_version"),
            "active_mode": session.get("active_mode") or "auto", "goal_id": session.get("goal_id"),
            "has_current_goal": bool(str(session.get("current_goal") or "").strip()),
            "has_summary": bool(str(conversation.get("summary") or "").strip()),
            "pending_question_count": len(conversation.get("pending_questions", [])) if isinstance(conversation.get("pending_questions"), list) else 0,
            "recent_reference_count": len(conversation.get("recent_references", [])) if isinstance(conversation.get("recent_references"), list) else 0,
        },
        "recent_message_count": len(messages), "context_snapshot_count": len(snapshots),
        "recovery_available": bool(snapshots) and session.get("status") != "closed",
    }


@router.get("/sessions/{session_id}/related-workflows")
def session_related_workflows(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    limit = _int_param(limit, 50, 1, 200)
    try:
        session = SessionManagerService().get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        workflows = WorkItemService().list_workflows(session_id=session_id, limit=limit)
    except HTTPException:
        raise
    except (PersistenceIntegrityError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Session or workflow data is unavailable") from exc
    return {"success": True, "session_id": session_id, "count": len(workflows), "workflows": workflows}
