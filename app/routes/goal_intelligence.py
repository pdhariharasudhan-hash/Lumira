from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.services.memory.memory_service import MemoryService, MemoryValidationError
from app.services.persistence.atomic_json_store import PersistenceIntegrityError

router = APIRouter()

def _int_param(value, default, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(minimum, min(maximum, value))


class BulkGoalUpdate(BaseModel):
    goal_ids: list[str] = Field(min_length=1, max_length=50)
    status: Literal["active", "paused", "completed", "blocked", "cancelled"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    project_id: str | None = Field(default=None, max_length=100)
    set_project: bool = False

    @field_validator("goal_ids")
    @classmethod
    def clean_ids(cls, values: list[str]) -> list[str]:
        result = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        if len(result) != len(values) or len(set(result)) != len(result):
            raise ValueError("goal_ids must be unique non-empty strings")
        return result


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    deadline: str | None = Field(default=None, max_length=40)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("deadline")
    @classmethod
    def clean_deadline(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("deadline must be ISO 8601") from exc
        return value


def _memory_and_goals(project_id: str | None = None, include_archived: bool = False):
    # Direct function calls receive FastAPI Query defaults rather than None.
    if not isinstance(project_id, str):
        project_id = None
    memory = MemoryService()
    goals = memory.get_all().get("goals", [])
    goals = [
        item for item in goals if isinstance(item, dict)
        and (include_archived or not item.get("archived"))
        and (project_id is None or item.get("project_id") == project_id)
    ]
    return memory, goals


def _goal_or_404(goals: list[dict], goal_id: str) -> dict:
    goal = next((item for item in goals if item.get("goal_id") == goal_id), None)
    if goal is None:
        raise HTTPException(status_code=404, detail="goal not found")
    return goal


@router.get("/goals/intelligence")
def get_goal_intelligence(
    project_id: str | None = Query(default=None, max_length=100),
    stale_days: int = Query(default=14, ge=1, le=365),
):
    """A deterministic 28-signal goal portfolio intelligence report; no model guesses."""
    try:
        _, goals = _memory_and_goals(project_id)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Goal memory is unavailable") from exc
    stale_days = _int_param(stale_days, 14, 1, 365)
    now = datetime.now(UTC)
    def parse_date(value):
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except ValueError:
            return None
    def updated_at(goal):
        return parse_date(goal.get("updated_at") or goal.get("created_at"))
    status = {name: sum(1 for g in goals if g.get("status") == name)
              for name in ("active", "paused", "completed", "blocked", "cancelled")}
    priority = {name: sum(1 for g in goals if g.get("priority") == name)
                for name in ("low", "normal", "high", "urgent")}
    active = [g for g in goals if g.get("status") == "active"]
    open_goals = [g for g in goals if g.get("status") not in {"completed", "cancelled"}]
    overdue, due_7, due_30, no_deadline, invalid_deadline = [], [], [], 0, []
    stale, no_progress, unowned_project, no_objective = [], [], [], []
    blocked_items, missing_dependencies, completed_dependencies = [], [], []
    all_ids = {g.get("goal_id") for g in goals}
    parent_ids = {g.get("parent_goal_id") for g in goals if g.get("parent_goal_id")}
    for g in goals:
        gid = g.get("goal_id", "")
        deadline_raw = g.get("deadline")
        deadline = parse_date(deadline_raw)
        if not deadline_raw:
            no_deadline += 1
        elif deadline is None:
            invalid_deadline.append(gid)
        elif g.get("status") != "completed":
            if deadline < now:
                overdue.append(gid)
            elif deadline <= now + timedelta(days=7):
                due_7.append(gid)
            elif deadline <= now + timedelta(days=30):
                due_30.append(gid)
        changed = updated_at(g)
        if g.get("status") not in {"completed", "cancelled"} and changed and changed < now - timedelta(days=stale_days):
            stale.append(gid)
        if g.get("status") == "active" and float(g.get("progress") or 0) <= 0:
            no_progress.append(gid)
        if not g.get("project_id"):
            unowned_project.append(gid)
        if not str(g.get("objective") or "").strip():
            no_objective.append(gid)
        if g.get("status") == "blocked" or g.get("blockers"):
            blocked_items.append(gid)
        for dep in g.get("dependencies", []) if isinstance(g.get("dependencies"), list) else []:
            target = next((item for item in goals if item.get("goal_id") == dep), None)
            if target is None:
                missing_dependencies.append({"goal_id": gid, "dependency_goal_id": dep})
            elif target.get("status") != "completed":
                completed_dependencies.append({"goal_id": gid, "dependency_goal_id": dep, "status": target.get("status")})
    parent_children = {}
    for g in goals:
        parent_children.setdefault(g.get("parent_goal_id"), []).append(g)
    rollups = []
    for parent_id, children in parent_children.items():
        if parent_id and parent_id in all_ids:
            progresses = [float(c.get("progress") or 0) for c in children]
            rollups.append({"goal_id": parent_id, "child_count": len(children),
                            "average_child_progress": round(sum(progresses) / len(progresses), 2) if progresses else 0})
    progress_values = [float(g.get("progress") or 0) for g in goals if isinstance(g.get("progress", 0), (int, float))]
    completed_count = status["completed"]
    denominator = max(1, completed_count + len(open_goals))
    recommendations = []
    for gid in overdue[:20]:
        recommendations.append({"goal_id": gid, "code": "overdue", "action": "Review deadline and next step"})
    for gid in blocked_items[:20]:
        recommendations.append({"goal_id": gid, "code": "blocked", "action": "Resolve or clarify blockers"})
    for gid in stale[:20]:
        recommendations.append({"goal_id": gid, "code": "stale", "action": "Review whether this goal is still active"})
    for gid in no_objective[:20]:
        recommendations.append({"goal_id": gid, "code": "objective_missing", "action": "Write a measurable objective"})
    projects = {}
    for g in goals:
        project = g.get("project_id") or "(unassigned)"
        projects[project] = projects.get(project, 0) + 1
    milestones_total = sum(len(g.get("milestones", [])) for g in goals if isinstance(g.get("milestones"), list))
    artifacts_total = sum(len(g.get("artifact_ids", [])) for g in goals if isinstance(g.get("artifact_ids"), list))
    child_count = sum(1 for g in goals if g.get("parent_goal_id") in all_ids)
    orphan_children = [g.get("goal_id") for g in goals if g.get("parent_goal_id") and g.get("parent_goal_id") not in all_ids]
    return {
        "generated_at": now.isoformat(), "project_id": project_id,
        "signals": {
            "01_total_goals": len(goals),
            "02_active_goals": status["active"],
            "03_paused_goals": status["paused"],
            "04_completed_goals": completed_count,
            "05_blocked_goals": status["blocked"],
            "06_cancelled_goals": status["cancelled"],
            "07_low_priority": priority["low"],
            "08_normal_priority": priority["normal"],
            "09_high_priority": priority["high"],
            "10_urgent_priority": priority["urgent"],
            "11_overdue_goal_ids": overdue[:100],
            "12_due_within_7_days": due_7[:100],
            "13_due_within_30_days": due_30[:100],
            "14_without_deadline": no_deadline,
            "15_invalid_deadline_ids": invalid_deadline[:100],
            "16_stale_goal_ids": stale[:100],
            "17_active_without_progress_ids": no_progress[:100],
            "18_goals_without_project_ids": unowned_project[:100],
            "19_goals_without_objective_ids": no_objective[:100],
            "20_blocked_or_has_blockers_ids": blocked_items[:100],
            "21_missing_dependency_edges": missing_dependencies[:100],
            "22_unmet_dependency_edges": completed_dependencies[:100],
            "23_average_progress": round(sum(progress_values) / len(progress_values), 2) if progress_values else 0,
            "24_completion_rate_percent": round(completed_count / denominator * 100, 2),
            "25_child_goal_count": child_count,
            "26_orphan_child_goal_ids": orphan_children[:100],
            "27_milestone_count": milestones_total,
            "28_artifact_link_count": artifacts_total,
        },
        "project_distribution": dict(sorted(projects.items(), key=lambda item: (-item[1], item[0]))[:50]),
        "child_progress_rollups": rollups[:100],
        "recommendations": recommendations[:50],
        "limits": {"max_goals_scanned": len(goals), "max_returned_ids_per_signal": 100},
    }


@router.get("/goals/search")
def search_goals(
    q: str = Query(min_length=1, max_length=200),
    project_id: str | None = Query(default=None, max_length=100),
    status: Literal["active", "paused", "completed", "blocked", "cancelled"] | None = None,
    limit: int = Query(default=30, ge=1, le=100),
):
    limit = _int_param(limit, 30, 1, 100)
    query = q.strip().casefold()
    if not query:
        raise HTTPException(status_code=422, detail="search query must not be empty")
    try:
        _, goals = _memory_and_goals(project_id)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Goal memory is unavailable") from exc
    results = []
    for goal in goals:
        if status and goal.get("status") != status:
            continue
        searchable = " ".join(str(goal.get(key) or "") for key in ("title", "objective", "project_id", "status", "priority")).casefold()
        if query in searchable:
            results.append(goal)
    results.sort(key=lambda g: (g.get("updated_at", ""), g.get("goal_id", "")), reverse=True)
    return {"query": q.strip(), "total": len(results), "goals": results[:limit]}


@router.get("/goals/timeline")
def get_goal_timeline(
    project_id: str | None = Query(default=None, max_length=100),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=300),
):
    try:
        _, goals = _memory_and_goals(project_id)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Goal memory is unavailable") from exc
    days = _int_param(days, 30, 1, 365)
    limit = _int_param(limit, 100, 1, 300)
    cutoff = datetime.now(UTC) - timedelta(days=days)
    events = []
    for goal in goals:
        history = goal.get("history", [])
        if not isinstance(history, list):
            continue
        for event in history[-50:]:
            if not isinstance(event, dict):
                continue
            raw = event.get("at")
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
            except ValueError:
                continue
            if parsed >= cutoff:
                events.append({"goal_id": goal.get("goal_id"), "goal_title": goal.get("title", ""), **event})
    events.sort(key=lambda item: str(item.get("at", "")), reverse=True)
    return {"events": events[:limit], "total": len(events), "days": days}


@router.get("/goals/next-actions")
def get_goal_next_actions(
    project_id: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
):
    try:
        _, goals = _memory_and_goals(project_id)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Goal memory is unavailable") from exc
    limit = _int_param(limit, 10, 1, 50)
    by_id = {g.get("goal_id"): g for g in goals}
    now = datetime.now(UTC)
    scored = []
    for goal in goals:
        if goal.get("status") != "active":
            continue
        blockers = goal.get("blockers", []) if isinstance(goal.get("blockers"), list) else []
        deps = goal.get("dependencies", []) if isinstance(goal.get("dependencies"), list) else []
        unmet = [dep for dep in deps if dep not in by_id or by_id[dep].get("status") != "completed"]
        deadline = None
        raw = goal.get("deadline")
        if raw:
            try:
                deadline = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=UTC)
            except ValueError:
                deadline = None
        if blockers or unmet:
            continue
        priority_score = {"urgent": 400, "high": 300, "normal": 200, "low": 100}.get(goal.get("priority"), 0)
        due_score = 150 if deadline and deadline < now + timedelta(days=7) else 0
        raw_progress = goal.get("progress", 0)
        try:
            numeric_progress = float(raw_progress) if not isinstance(raw_progress, bool) else 0.0
        except (TypeError, ValueError):
            numeric_progress = 0.0
        progress_score = 100 - min(100, max(0, numeric_progress))
        scored.append((priority_score + due_score + progress_score, goal))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("deadline") or "9999"), str(item[1].get("goal_id"))))
    return {"actions": [{"goal": goal, "reason": "active, unblocked, dependencies satisfied; ranked by priority, due date, and remaining progress"}
                        for _, goal in scored[:limit]], "total_eligible": len(scored)}


@router.get("/goals/{goal_id}/milestones")
def list_goal_milestones(goal_id: str):
    try:
        _, goals = _memory_and_goals(include_archived=True)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Goal memory is unavailable") from exc
    goal = _goal_or_404(goals, goal_id)
    milestones = goal.get("milestones", [])
    if not isinstance(milestones, list):
        raise HTTPException(status_code=409, detail="stored milestone data is invalid")
    return {"goal_id": goal_id, "milestones": milestones, "total": len(milestones)}


@router.post("/goals/{goal_id}/milestones")
def add_goal_milestone(goal_id: str, request: MilestoneCreate):
    try:
        memory, goals = _memory_and_goals()
        goal = _goal_or_404(goals, goal_id)
        milestones = goal.get("milestones", [])
        if not isinstance(milestones, list):
            raise HTTPException(status_code=409, detail="stored milestone data is invalid")
        if any(str(item.get("title", "")).casefold() == request.title.casefold() for item in milestones if isinstance(item, dict)):
            raise HTTPException(status_code=409, detail="milestone title already exists")
        if len(milestones) >= 50:
            raise HTTPException(status_code=409, detail="goal already has 50 milestones")
        milestone = {"milestone_id": f"ms_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}", "title": request.title,
                     "status": "pending", "deadline": request.deadline, "created_at": datetime.now(UTC).isoformat()}
        updated = memory.update_goal(goal_id, milestones=[*milestones, milestone])
        return {"goal": updated, "milestone": milestone}
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/goals/{goal_id}/milestones/{milestone_id}")
def update_goal_milestone(
    goal_id: str,
    milestone_id: str,
    status: Literal["pending", "in_progress", "completed", "blocked"] = Query(...),
):
    try:
        memory, goals = _memory_and_goals()
        goal = _goal_or_404(goals, goal_id)
        milestones = goal.get("milestones", [])
        if not isinstance(milestones, list):
            raise HTTPException(status_code=409, detail="stored milestone data is invalid")
        found = False
        updated_milestones = []
        for item in milestones:
            if isinstance(item, dict) and item.get("milestone_id") == milestone_id:
                item = {**item, "status": status, "updated_at": datetime.now(UTC).isoformat()}
                if status == "completed":
                    item["completed_at"] = datetime.now(UTC).isoformat()
                found = True
            updated_milestones.append(item)
        if not found:
            raise HTTPException(status_code=404, detail="milestone not found")
        updated = memory.update_goal(goal_id, milestones=updated_milestones)
        return {"goal": updated, "milestone_id": milestone_id, "status": status}
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/goals/{goal_id}/milestones/{milestone_id}")
def remove_goal_milestone(goal_id: str, milestone_id: str):
    try:
        memory, goals = _memory_and_goals()
        goal = _goal_or_404(goals, goal_id)
        milestones = goal.get("milestones", [])
        remaining = [item for item in milestones if not (isinstance(item, dict) and item.get("milestone_id") == milestone_id)]
        if len(remaining) == len(milestones):
            raise HTTPException(status_code=404, detail="milestone not found")
        return {"goal": memory.update_goal(goal_id, milestones=remaining), "removed_milestone_id": milestone_id}
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/goals/bulk-update")
def bulk_update_goals(request: BulkGoalUpdate):
    updates = {}
    if request.status is not None:
        updates["status"] = request.status
    if request.priority is not None:
        updates["priority"] = request.priority
    if request.set_project:
        updates["project_id"] = request.project_id
    if not updates:
        raise HTTPException(status_code=422, detail="at least one update field is required")
    try:
        memory, goals = _memory_and_goals()
        by_id = {g.get("goal_id"): g for g in goals}
        missing = [gid for gid in request.goal_ids if gid not in by_id]
        if missing:
            raise HTTPException(status_code=404, detail={"message": "one or more goals not found", "missing_goal_ids": missing})
        if request.status == "completed":
            blocked = [gid for gid in request.goal_ids if by_id[gid].get("blockers") or any(
                dep not in by_id or by_id[dep].get("status") != "completed"
                for dep in by_id[gid].get("dependencies", []) if isinstance(dep, str))]
            if blocked:
                raise HTTPException(status_code=409, detail={"message": "resolve blockers and dependencies before completing goals", "goal_ids": blocked})
        updated = [memory.update_goal(gid, **updates) for gid in request.goal_ids]
        return {"updated": updated, "count": len(updated), "fields": sorted(updates)}
    except HTTPException:
        raise
    except (KeyError, MemoryValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/goals/{goal_id}/archive")
def archive_goal(goal_id: str):
    try:
        _, goals = _memory_and_goals()
        _goal_or_404(goals, goal_id)
        if any(g.get("parent_goal_id") == goal_id and not g.get("archived") for g in goals):
            raise HTTPException(status_code=409, detail="archive active child goals first")
        if not MemoryService().archive("goals", goal_id):
            raise HTTPException(status_code=404, detail="goal not found")
        return {"goal_id": goal_id, "archived": True}
    except HTTPException:
        raise
    except MemoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/goals/{goal_id}/restore")
def restore_goal(goal_id: str):
    try:
        memory = MemoryService()
        def restore(document):
            goals = document.get("goals", [])
            target = next((g for g in goals if isinstance(g, dict) and g.get("goal_id") == goal_id), None)
            if target is None:
                return False
            target.pop("archived", None)
            target.pop("archived_at", None)
            target["updated_at"] = datetime.now(UTC).isoformat()
            return True
        restored = memory.cognitive_store.update(restore, memory._default_cognitive_memory())
        if not restored:
            raise HTTPException(status_code=404, detail="goal not found")
        return {"goal_id": goal_id, "archived": False}
    except HTTPException:
        raise
    except (MemoryValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Goal memory is unavailable") from exc


@router.post("/goals/{goal_id}/duplicate")
def duplicate_goal(goal_id: str, include_children: bool = Query(default=False)):
    try:
        memory, goals = _memory_and_goals()
        original = _goal_or_404(goals, goal_id)
        new_goal = memory.create_goal(
            title=f"{str(original.get('title') or 'Goal')[:480]} (copy)",
            objective=str(original.get("objective") or "")[:2000],
            priority=original.get("priority", "normal"),
            project_id=original.get("project_id"),
            deadline=original.get("deadline"),
        )
        copied_milestones = []
        for item in original.get("milestones", []) if isinstance(original.get("milestones"), list) else []:
            if isinstance(item, dict):
                copied_milestones.append({"title": str(item.get("title") or "Milestone")[:300], "status": "pending",
                                          "deadline": item.get("deadline") if isinstance(item.get("deadline"), str) else None})
        if copied_milestones:
            new_goal = memory.update_goal(new_goal["goal_id"], milestones=copied_milestones[:50])
        children_copied = 0
        if include_children:
            children = [g for g in goals if g.get("parent_goal_id") == goal_id][:20]
            if children:
                created = memory.decompose_goal(new_goal["goal_id"], [str(c.get("title") or "Objective")[:500] for c in children])
                children_copied = len(created.get("objectives", []))
        return {"original_goal_id": goal_id, "goal": new_goal, "children_copied": children_copied}
    except HTTPException:
        raise
    except (KeyError, MemoryValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/goals/{goal_id}/rollup")
def get_goal_rollup(goal_id: str):
    try:
        _, goals = _memory_and_goals()
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Goal memory is unavailable") from exc
    goal = _goal_or_404(goals, goal_id)
    children = [g for g in goals if g.get("parent_goal_id") == goal_id]
    progress = [float(g.get("progress") or 0) for g in children]
    statuses = {s: sum(1 for g in children if g.get("status") == s) for s in ("active", "paused", "completed", "blocked", "cancelled")}
    return {"goal_id": goal_id, "own_progress": float(goal.get("progress") or 0), "child_count": len(children),
            "child_status_counts": statuses, "average_child_progress": round(sum(progress) / len(progress), 2) if progress else 0,
            "completed_child_percent": round(statuses["completed"] / len(children) * 100, 2) if children else 0,
            "child_goal_ids": [g.get("goal_id") for g in children[:100]]}


@router.get("/goals/{goal_id}/compare/{other_goal_id}")
def compare_goals(goal_id: str, other_goal_id: str):
    try:
        _, goals = _memory_and_goals(include_archived=True)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Goal memory is unavailable") from exc
    left, right = _goal_or_404(goals, goal_id), _goal_or_404(goals, other_goal_id)
    fields = ("title", "objective", "status", "priority", "progress", "deadline", "project_id", "parent_goal_id", "dependencies", "blockers", "milestones", "artifact_ids")
    differences = {field: {"left": left.get(field), "right": right.get(field)} for field in fields if left.get(field) != right.get(field)}
    return {"left_goal_id": goal_id, "right_goal_id": other_goal_id, "identical_fields": [f for f in fields if left.get(f) == right.get(f)],
            "differences": differences, "difference_count": len(differences)}


@router.get("/goals/export")
def export_goals(
    project_id: str | None = Query(default=None, max_length=100),
    include_archived: bool = False,
    limit: int = Query(default=500, ge=1, le=1000),
):
    try:
        _, goals = _memory_and_goals(project_id, include_archived=include_archived)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=503, detail="Goal memory is unavailable") from exc
    goals.sort(key=lambda g: (g.get("created_at", ""), g.get("goal_id", "")))
    return {"schema_version": 1, "exported_at": datetime.now(UTC).isoformat(), "count": min(len(goals), limit),
            "truncated": len(goals) > limit, "goals": [deepcopy(g) for g in goals[:limit]]}
