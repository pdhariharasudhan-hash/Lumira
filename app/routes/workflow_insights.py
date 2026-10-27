from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict

from app.services.work_items.work_item_service import WorkItemService, WorkItemValidationError
from app.services.persistence.atomic_json_store import PersistenceIntegrityError

router = APIRouter()


def _service() -> WorkItemService:
    return WorkItemService()


def _workflows(limit: int = 200, **filters):
    try:
        return _service().list_workflows(limit=limit, **filters)
    except (WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Workflow data is unavailable or invalid") from exc


def _workflow_or_404(service: WorkItemService, workflow_id: str) -> dict:
    try:
        workflow = service.get_workflow(workflow_id)
    except PersistenceIntegrityError as exc:
        raise HTTPException(status_code=503, detail="Workflow data is unavailable or invalid") from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return workflow


def _parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


@router.get("/workflows/summary")
def workflow_summary(
    project_id: Annotated[str | None, Query(max_length=100)] = None,
    category: Literal["business", "operations"] | None = None,
):
    workflows = _workflows(project_id=project_id, category=category, limit=200)
    status_counts = {status: 0 for status in ("planned", "in_progress", "blocked", "completed", "failed")}
    task_counts = {status: 0 for status in ("pending", "in_progress", "blocked", "completed", "failed")}
    blocked_workflows, failed_workflows, stale_workflows = [], [], []
    total_tasks = completed_tasks = 0
    cutoff = datetime.now(UTC) - timedelta(days=7)
    for workflow in workflows:
        status = workflow.get("status")
        if status in status_counts:
            status_counts[status] += 1
        tasks = workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []
        for task in tasks:
            state = task.get("status") if isinstance(task, dict) else None
            if state in task_counts:
                task_counts[state] += 1
            total_tasks += 1
            completed_tasks += state == "completed"
        if status == "blocked" or any(isinstance(task, dict) and task.get("status") == "blocked" for task in tasks):
            blocked_workflows.append(workflow.get("workflow_id"))
        if status == "failed" or any(isinstance(task, dict) and task.get("status") == "failed" for task in tasks):
            failed_workflows.append(workflow.get("workflow_id"))
        updated = _parse_time(workflow.get("updated_at"))
        if status not in {"completed"} and updated and updated < cutoff:
            stale_workflows.append(workflow.get("workflow_id"))
    return {
        "success": True, "generated_at": datetime.now(UTC).isoformat(),
        "filters": {"project_id": project_id, "category": category},
        "scanned_workflows": len(workflows), "truncated": len(workflows) >= 200,
        "workflow_status_counts": status_counts, "task_status_counts": task_counts,
        "total_tasks": total_tasks,
        "task_completion_percent": round(completed_tasks / total_tasks * 100, 2) if total_tasks else 0,
        "blocked_workflow_ids": blocked_workflows[:100],
        "failed_workflow_ids": failed_workflows[:100],
        "stale_workflow_ids": stale_workflows[:100],
    }


@router.get("/workflows/attention")
def workflow_attention(
    project_id: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=7)
    candidates = []
    for workflow in _workflows(project_id=project_id, limit=200):
        tasks = workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []
        failed = [t for t in tasks if isinstance(t, dict) and t.get("status") == "failed"]
        blocked = [t for t in tasks if isinstance(t, dict) and t.get("status") == "blocked"]
        updated = _parse_time(workflow.get("updated_at"))
        stale = bool(updated and updated < cutoff and workflow.get("status") != "completed")
        if not (failed or blocked or stale):
            continue
        score = len(failed) * 100 + len(blocked) * 50 + (20 if stale else 0)
        candidates.append((score, {
            "workflow_id": workflow.get("workflow_id"), "title": workflow.get("title"),
            "project_id": workflow.get("project_id"), "goal_id": workflow.get("goal_id"),
            "status": workflow.get("status"), "updated_at": workflow.get("updated_at"),
            "failed_task_count": len(failed), "blocked_task_count": len(blocked), "stale": stale,
            "recommended_action": "inspect_failed_tasks" if failed else "resolve_blockers" if blocked else "review_stale_workflow",
        }))
    candidates.sort(key=lambda item: (-item[0], str(item[1].get("updated_at") or "")))
    return {"success": True, "items": [item for _, item in candidates[:limit]], "total_attention_items": len(candidates)}


@router.get("/workflows/timeline")
def workflow_timeline(
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    project_id: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    cutoff = datetime.now(UTC) - timedelta(days=days)
    events = []
    for workflow in _workflows(project_id=project_id, limit=200):
        for task in workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []:
            if not isinstance(task, dict):
                continue
            for event in task.get("history", [])[-20:] if isinstance(task.get("history"), list) else []:
                if not isinstance(event, dict):
                    continue
                parsed = _parse_time(event.get("at"))
                if parsed is None or parsed < cutoff:
                    continue
                events.append({
                    "workflow_id": workflow.get("workflow_id"), "workflow_title": workflow.get("title"),
                    "task_id": task.get("task_id"), "task_title": task.get("title"),
                    "project_id": workflow.get("project_id"), **deepcopy(event),
                })
    events.sort(key=lambda item: str(item.get("at", "")), reverse=True)
    return {"success": True, "days": days, "events": events[:limit], "total_events": len(events)}


@router.get("/workflows/search")
def search_workflows(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    status: Literal["planned", "in_progress", "blocked", "completed", "failed"] | None = None,
    project_id: Annotated[str | None, Query(max_length=100)] = None,
    category: Literal["business", "operations"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
):
    query = q.strip().casefold()
    if not query:
        raise HTTPException(status_code=422, detail="search query must not be empty")
    results = []
    for workflow in _workflows(project_id=project_id, category=category, limit=200):
        if status and workflow.get("status") != status:
            continue
        fields = [workflow.get(key, "") for key in ("title", "request", "workflow_id", "project_id", "goal_id")]
        fields.extend(task.get("title", "") for task in workflow.get("tasks", []) if isinstance(task, dict))
        if query in " ".join(str(value or "") for value in fields).casefold():
            results.append(workflow)
    results.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("workflow_id", ""))), reverse=True)
    return {"success": True, "query": q.strip(), "total": len(results), "workflows": results[:limit]}


@router.get("/workflows/export")
def export_workflows(
    project_id: Annotated[str | None, Query(max_length=100)] = None,
    category: Literal["business", "operations"] | None = None,
    status: Literal["planned", "in_progress", "blocked", "completed", "failed"] | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    workflows = _workflows(project_id=project_id, category=category, limit=200)
    if status:
        workflows = [item for item in workflows if item.get("status") == status]
    workflows.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("workflow_id", ""))))
    return {"success": True, "schema_version": 1, "exported_at": datetime.now(UTC).isoformat(),
            "count": min(len(workflows), limit), "truncated": len(workflows) > limit,
            "workflows": [deepcopy(item) for item in workflows[:limit]]}


@router.get("/workflows/{workflow_id}/dependency-graph")
def workflow_dependency_graph(workflow_id: str):
    workflow = _workflow_or_404(_service(), workflow_id)
    tasks = workflow.get("tasks", [])
    nodes = [{"task_id": task.get("task_id"), "title": task.get("title"), "status": task.get("status")}
             for task in tasks if isinstance(task, dict)]
    edges = [{"from": dependency, "to": task.get("task_id")}
             for task in tasks if isinstance(task, dict)
             for dependency in task.get("dependencies", []) if isinstance(dependency, str)]
    return {"success": True, "workflow_id": workflow_id, "nodes": nodes, "edges": edges,
            "node_count": len(nodes), "edge_count": len(edges)}


def _task(workflow: dict, task_id: str) -> dict:
    task = next((item for item in workflow.get("tasks", []) if isinstance(item, dict) and item.get("task_id") == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/workflows/{workflow_id}/tasks/{task_id}/retry")
def retry_failed_task(workflow_id: str, task_id: str):
    service = _service()
    workflow = _workflow_or_404(service, workflow_id)
    task = _task(workflow, task_id)
    if task.get("status") != "failed":
        raise HTTPException(status_code=409, detail="only failed tasks can be retried")
    try:
        updated = service.update_task(workflow_id, task_id, "pending", blocker=None, result=None)
    except (KeyError, WorkItemValidationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "workflow": updated, "retried_task_id": task_id,
            "note": "Task returned to pending; dependencies must still be completed before it can start."}


@router.post("/workflows/{workflow_id}/tasks/{task_id}/unblock")
def unblock_task(workflow_id: str, task_id: str):
    service = _service()
    workflow = _workflow_or_404(service, workflow_id)
    task = _task(workflow, task_id)
    if task.get("status") != "blocked":
        raise HTTPException(status_code=409, detail="only blocked tasks can be unblocked")
    completed = {item.get("task_id") for item in workflow.get("tasks", []) if isinstance(item, dict) and item.get("status") == "completed"}
    unmet = [dep for dep in task.get("dependencies", []) if dep not in completed]
    if unmet:
        raise HTTPException(status_code=409, detail={"message": "task dependencies are not complete", "unmet_dependencies": unmet})
    try:
        updated = service.update_task(workflow_id, task_id, "pending", blocker=None, result=task.get("result"))
    except (KeyError, WorkItemValidationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "workflow": updated, "unblocked_task_id": task_id}


@router.post("/workflows/{workflow_id}/tasks/{task_id}/start")
def start_ready_task(workflow_id: str, task_id: str):
    service = _service()
    workflow = _workflow_or_404(service, workflow_id)
    task = _task(workflow, task_id)
    if task.get("status") != "pending":
        raise HTTPException(status_code=409, detail="only pending tasks can be started")
    completed = {item.get("task_id") for item in workflow.get("tasks", []) if isinstance(item, dict) and item.get("status") == "completed"}
    unmet = [dep for dep in task.get("dependencies", []) if dep not in completed]
    if unmet:
        raise HTTPException(status_code=409, detail={"message": "task dependencies are not complete", "unmet_dependencies": unmet})
    try:
        updated = service.update_task(workflow_id, task_id, "in_progress")
    except (KeyError, WorkItemValidationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "workflow": updated, "started_task_id": task_id}


@router.post("/workflows/{workflow_id}/tasks/{task_id}/complete")
def complete_active_task(workflow_id: str, task_id: str):
    service = _service()
    workflow = _workflow_or_404(service, workflow_id)
    task = _task(workflow, task_id)
    if task.get("status") != "in_progress":
        raise HTTPException(status_code=409, detail="task must be in progress before completion")
    try:
        updated = service.update_task(workflow_id, task_id, "completed", blocker=None, result=task.get("result"))
    except (KeyError, WorkItemValidationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "workflow": updated, "completed_task_id": task_id}


class TaskReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)
    result: str | None = Field(default=None, max_length=4000)


@router.get("/workflows/metrics/by-project")
def workflow_metrics_by_project():
    workflows = _workflows(limit=200)
    groups = {}
    for workflow in workflows:
        project = workflow.get("project_id") or "(unassigned)"
        item = groups.setdefault(project, {"project_id": project, "workflow_count": 0, "completed": 0, "blocked": 0, "failed": 0, "task_count": 0, "completed_tasks": 0})
        item["workflow_count"] += 1
        status = workflow.get("status")
        if status in {"completed", "blocked", "failed"}:
            item[status] += 1
        for task in workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []:
            if not isinstance(task, dict):
                continue
            item["task_count"] += 1
            item["completed_tasks"] += task.get("status") == "completed"
    result = []
    for item in groups.values():
        item["task_completion_percent"] = round(item["completed_tasks"] / item["task_count"] * 100, 2) if item["task_count"] else 0
        result.append(item)
    result.sort(key=lambda item: (-item["workflow_count"], item["project_id"]))
    return {"success": True, "scanned_workflows": len(workflows), "truncated": len(workflows) >= 200, "projects": result[:100]}


@router.get("/workflows/{workflow_id}/ready-tasks")
def ready_workflow_tasks(workflow_id: str):
    try:
        progress = _service().get_workflow_progress(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workflow not found") from exc
    except (WorkItemValidationError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Workflow data is unavailable or invalid") from exc
    return {"success": True, "workflow_id": workflow_id, "ready_tasks": progress.get("ready_tasks", []),
            "active_tasks": progress.get("active_tasks", []), "blocked_tasks": progress.get("blocked_tasks", []),
            "failed_tasks": progress.get("failed_tasks", []), "progress": progress.get("progress", {})}


@router.get("/workflows/{workflow_id}/health")
def workflow_health(workflow_id: str, stale_days: Annotated[int, Query(ge=1, le=365)] = 7):
    workflow = _workflow_or_404(_service(), workflow_id)
    now = datetime.now(UTC)
    updated = _parse_time(workflow.get("updated_at"))
    tasks = workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []
    task_ids = {task.get("task_id") for task in tasks if isinstance(task, dict)}
    findings = []
    for task in tasks:
        if not isinstance(task, dict):
            findings.append({"code": "invalid_task_record"})
            continue
        for dependency in task.get("dependencies", []) if isinstance(task.get("dependencies"), list) else []:
            if dependency not in task_ids:
                findings.append({"code": "missing_task_dependency", "task_id": task.get("task_id"), "dependency_task_id": dependency})
        if task.get("status") == "in_progress":
            task_updated = _parse_time(task.get("updated_at"))
            if task_updated and task_updated < now - timedelta(days=stale_days):
                findings.append({"code": "stale_in_progress_task", "task_id": task.get("task_id"), "updated_at": task.get("updated_at")})
    if updated and updated < now - timedelta(days=stale_days) and workflow.get("status") != "completed":
        findings.append({"code": "stale_workflow", "updated_at": workflow.get("updated_at")})
    if workflow.get("status") == "failed":
        findings.append({"code": "workflow_has_failure"})
    if workflow.get("status") == "blocked":
        findings.append({"code": "workflow_is_blocked"})
    return {"success": True, "workflow_id": workflow_id, "status": workflow.get("status"),
            "stale_days_threshold": stale_days, "finding_count": len(findings), "findings": findings,
            "is_healthy": not findings}


@router.post("/workflows/{workflow_id}/tasks/{task_id}/block")
def block_workflow_task(workflow_id: str, task_id: str, request: TaskReasonRequest):
    service = _service()
    workflow = _workflow_or_404(service, workflow_id)
    task = _task(workflow, task_id)
    if task.get("status") not in {"pending", "in_progress"}:
        raise HTTPException(status_code=409, detail="only pending or in-progress tasks can be blocked")
    try:
        updated = service.update_task(workflow_id, task_id, "blocked", blocker=request.reason, result=request.result)
    except (KeyError, WorkItemValidationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "workflow": updated, "blocked_task_id": task_id}


@router.post("/workflows/{workflow_id}/tasks/{task_id}/fail")
def fail_workflow_task(workflow_id: str, task_id: str, request: TaskReasonRequest):
    service = _service()
    workflow = _workflow_or_404(service, workflow_id)
    task = _task(workflow, task_id)
    if task.get("status") != "in_progress":
        raise HTTPException(status_code=409, detail="only in-progress tasks can be marked failed")
    try:
        updated = service.update_task(workflow_id, task_id, "failed", blocker=request.reason, result=request.result)
    except (KeyError, WorkItemValidationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "workflow": updated, "failed_task_id": task_id}


@router.get("/workflows/{workflow_id}/task-results")
def workflow_task_results(workflow_id: str):
    workflow = _workflow_or_404(_service(), workflow_id)
    results = []
    for task in workflow.get("tasks", []) if isinstance(workflow.get("tasks"), list) else []:
        if isinstance(task, dict) and (task.get("result") or task.get("blocker")):
            results.append({"task_id": task.get("task_id"), "title": task.get("title"), "status": task.get("status"),
                            "result": task.get("result"), "blocker": task.get("blocker"), "updated_at": task.get("updated_at")})
    return {"success": True, "workflow_id": workflow_id, "count": len(results), "task_results": results[:20]}
