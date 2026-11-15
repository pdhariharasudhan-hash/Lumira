"""Owner-controlled background task submission, recovery and cancellation routes."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.services.background_tasks.background_agent_task_service import BackgroundAgentTaskService
from app.services.background_tasks.background_agent_worker_service import BackgroundAgentWorkerService
from app.services.security.security_audit_log_service import SecurityAuditLogService

router = APIRouter(prefix="/background-tasks", tags=["Background Tasks"])
service = BackgroundAgentTaskService()
worker = BackgroundAgentWorkerService(task_service=service)


class BackgroundTaskRetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool


class BackgroundTaskDispatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool
    limit: int = Field(default=3, ge=1, le=5)


class BackgroundTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=10_000)
    agent_name: str | None = Field(default=None, pattern="^(planner_agent|research_agent|code_agent)$")
    autonomous: StrictBool = False
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


def _audit(action: str, outcome: str, details: dict) -> None:
    SecurityAuditLogService().append(
        event_type="background_agent_worker",
        action=action,
        outcome=outcome,
        actor="local_owner",
        details=details,
    )


@router.post("", status_code=202)
def create_background_task(request: BackgroundTaskCreate, background_tasks: BackgroundTasks):
    try:
        _audit("task.create", "requested", {
            "agent_name": request.agent_name,
            "autonomous": request.autonomous,
            "idempotency_key": request.idempotency_key,
        })
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Task creation was blocked because the audit log is unavailable.") from exc

    created = service.create(
        request.task,
        request.agent_name,
        request.autonomous,
        idempotency_key=request.idempotency_key,
    )
    if not created.get("success"):
        raise HTTPException(status_code=422, detail=created)
    task = created["task"]
    task_id = task["task_id"]
    try:
        _audit("task.create", "completed", {
            "task_id": task_id,
            "duplicate": created.get("duplicate", False),
            "status": task.get("status"),
        })
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "task_create_audit_failed", "task_id": task_id, "side_effect_may_have_occurred": True},
        ) from exc
    if task.get("status") == "queued":
        background_tasks.add_task(worker.execute, task_id)
    return {
        "success": True,
        "duplicate": created.get("duplicate", False),
        "status": task.get("status"),
        "task": task,
    }


@router.get("")
def list_background_tasks(
    status: str | None = Query(default=None, pattern="^(queued|running|completed|failed|interrupted|cancelled)$"),
    limit: int = Query(default=100, ge=1, le=200),
):
    return service.list(status, limit)


@router.post("/dispatch-queued", status_code=202)
def dispatch_queued_background_tasks(request: BackgroundTaskDispatch, background_tasks: BackgroundTasks):
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    try:
        _audit("task.dispatch_queued", "requested", {"limit": request.limit})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Queued work was not dispatched because the audit log is unavailable.") from exc
    result = service.list(status="queued", limit=request.limit)
    if result.get("success") is not True:
        raise HTTPException(status_code=503, detail=result)
    task_ids = [
        item.get("task_id")
        for item in result.get("tasks", [])
        if isinstance(item, dict) and isinstance(item.get("task_id"), str)
    ]
    for task_id in task_ids:
        background_tasks.add_task(worker.execute, task_id)
    try:
        _audit("task.dispatch_queued", "completed", {"task_ids": task_ids})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "queued_dispatch_audit_failed", "task_ids": task_ids, "side_effect_may_have_occurred": bool(task_ids)},
        ) from exc
    return {
        "success": True,
        "dispatched_count": len(task_ids),
        "task_ids": task_ids,
        "message": "Queued jobs submitted to the RAM-aware worker; execution may be deferred under resource pressure.",
    }


@router.post("/{task_id}/retry", status_code=202)
def retry_background_task(task_id: str, request: BackgroundTaskRetry, background_tasks: BackgroundTasks):
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    try:
        _audit("task.retry", "requested", {"task_id": task_id})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Task retry was blocked because the audit log is unavailable.") from exc
    result = service.retry(task_id, owner_confirmed=request.confirm)
    if result.get("success") is not True:
        code = result.get("code")
        status = 404 if code == "task_not_found" else 403 if code and code.startswith("autonomous_") else 409
        raise HTTPException(status_code=status, detail=result)
    try:
        _audit("task.retry", "completed", {"task_id": task_id, "retry_count": result["task"].get("retry_count", 0)})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "task_retry_audit_failed", "task_id": task_id, "side_effect_may_have_occurred": True},
        ) from exc
    background_tasks.add_task(worker.execute, task_id)
    return {"success": True, "status": "queued", "task": result["task"]}


@router.post("/{task_id}/cancel")
def cancel_background_task(task_id: str, request: BackgroundTaskRetry):
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    try:
        _audit("task.cancel", "requested", {"task_id": task_id})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Task cancellation was blocked because the audit log is unavailable.") from exc
    result = service.cancel(task_id, owner_confirmed=request.confirm)
    if result.get("success") is not True:
        code = result.get("code")
        status = 404 if code == "task_not_found" else 409
        raise HTTPException(status_code=status, detail=result)
    try:
        _audit("task.cancel", "completed", {"task_id": task_id})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "task_cancel_audit_failed", "task_id": task_id, "side_effect_may_have_occurred": True},
        ) from exc
    return {"success": True, "status": "cancelled", "task": result["task"]}


@router.get("/{task_id}")
def get_background_task(task_id: str):
    task = service.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Background task not found.")
    return {"success": True, "task": task}
