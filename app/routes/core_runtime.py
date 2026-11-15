"""Core event bus, durable queue, and owner-controlled scheduler routes."""
from __future__ import annotations

from typing import Any
import hashlib

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.services.system.event_bus_service import EventBusService
from app.services.system.message_queue_service import MessageQueueService
from app.services.system.task_scheduler_service import TaskSchedulerService
from app.services.system.scheduled_task_dispatch_service import ScheduledTaskDispatchService
from app.services.background_tasks.background_agent_worker_service import BackgroundAgentWorkerService
from app.services.security.security_audit_log_service import SecurityAuditLogService

router = APIRouter(prefix="/core", tags=["core-runtime"])


class EventPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    source: str = Field(default="local_api", min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class QueueEnqueueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=128)
    body: dict[str, Any] = Field(default_factory=dict)
    dedupe_key: str | None = Field(default=None, max_length=256)
    max_attempts: int = Field(default=3, ge=1, le=5)


class QueueClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str | None = Field(default=None, max_length=128)


class QueueAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_token: str = Field(min_length=1, max_length=128)
    success: StrictBool
    error: str | None = Field(default=None, max_length=500)
    retry_delay_seconds: int = Field(default=30, ge=0, le=86400)


class ScheduleOnceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=10000)
    run_at: str = Field(min_length=1, max_length=64)
    owner_approved: StrictBool
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScheduleIntervalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=10000)
    first_run_at: str = Field(min_length=1, max_length=64)
    interval_seconds: int = Field(ge=60, le=31536000)
    max_runs: int = Field(ge=1, le=1000)
    owner_approved: StrictBool
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScheduleFinishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: StrictBool
    error: str | None = Field(default=None, max_length=500)


class ScheduleCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool


class DispatchDueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool
    limit: int = Field(default=1, ge=1, le=5)


class SyncScheduleResultsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=20, ge=1, le=100)


def _audit(action: str, outcome: str, details: dict) -> None:
    SecurityAuditLogService().append(
        event_type="core_runtime",
        action=action,
        outcome=outcome,
        actor="local_owner",
        details=details,
    )


def _status_for(result: dict) -> int:
    code = result.get("code")
    if code and code.endswith("_unavailable"):
        return 503
    if code in {"message_not_found", "job_not_found"}:
        return 404
    if code in {"explicit_owner_approval_required", "explicit_owner_confirmation_required", "job_not_cancellable", "message_not_claimed", "job_not_claimed"}:
        return 409
    if code in {"invalid_task", "invalid_run_at", "timezone_required", "run_at_must_be_future", "invalid_recurrence", "invalid_limit", "invalid_message", "invalid_topic", "invalid_metadata", "metadata_too_large", "metadata_not_json"}:
        return 422
    return 409


@router.post("/events", status_code=202)
def publish_core_event(request: EventPublishRequest):
    try:
        _audit("event.publish", "requested", {"name": request.name, "source": request.source})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Event publication was blocked because the audit log is unavailable.") from exc
    result = EventBusService().publish(request.name, request.payload, source=request.source)
    if result.get("success") is not True:
        raise HTTPException(status_code=503, detail=result)
    event = result.get("event") or {}
    try:
        _audit("event.publish", "completed", {"event_id": event.get("event_id"), "name": request.name})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "event_publish_audit_failed", "side_effect_may_have_occurred": True, "event_id": event.get("event_id")},
        ) from exc
    return result


@router.get("/events")
def list_core_events(name: str | None = None, after: str | None = None, limit: int = 100):
    result = EventBusService().list_events(name=name, after=after, limit=limit)
    if result.get("success") is not True:
        raise HTTPException(status_code=422 if result.get("code") in {"invalid_limit", "invalid_event_name", "cursor_not_found"} else 503, detail=result)
    return result


@router.post("/queue", status_code=202)
def enqueue_core_message(request: QueueEnqueueRequest):
    try:
        _audit("queue.enqueue", "requested", {"topic": request.topic, "dedupe_key": request.dedupe_key})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Queue insertion was blocked because the audit log is unavailable.") from exc
    result = MessageQueueService().enqueue(
        request.topic,
        request.body,
        dedupe_key=request.dedupe_key,
        max_attempts=request.max_attempts,
    )
    if result.get("success") is not True:
        raise HTTPException(status_code=_status_for(result), detail=result)
    message = result.get("message") or {}
    try:
        _audit("queue.enqueue", "completed", {"message_id": message.get("message_id"), "topic": request.topic})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "queue_enqueue_audit_failed", "side_effect_may_have_occurred": True, "message_id": message.get("message_id")},
        ) from exc
    return result


@router.get("/queue")
def list_core_messages(status: str | None = None, limit: int = 100):
    result = MessageQueueService().list(status=status, limit=limit)
    if result.get("success") is not True:
        raise HTTPException(status_code=422 if result.get("code") in {"invalid_status", "invalid_limit"} else 503, detail=result)
    return result


@router.post("/queue/claim")
def claim_core_message(request: QueueClaimRequest):
    try:
        _audit("queue.claim", "requested", {"topic": request.topic})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Queue claim was blocked because the audit log is unavailable.") from exc
    result = MessageQueueService().claim(topic=request.topic)
    if result.get("success") is not True:
        raise HTTPException(status_code=503, detail=result)
    claimed = result.get("message") or {}
    try:
        _audit("queue.claim", "completed" if claimed else "empty", {"message_id": claimed.get("message_id"), "topic": claimed.get("topic")})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "queue_claim_audit_failed", "side_effect_may_have_occurred": True, "message_id": claimed.get("message_id")},
        ) from exc
    return result


@router.post("/queue/{message_id}/ack")
def acknowledge_core_message(message_id: str, request: QueueAckRequest):
    try:
        _audit("queue.acknowledge", "requested", {"message_id": message_id, "success": request.success})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Queue acknowledgement was blocked because the audit log is unavailable.") from exc
    result = MessageQueueService().acknowledge(
        message_id,
        lease_token=request.lease_token,
        success=request.success,
        error=request.error,
        retry_delay_seconds=request.retry_delay_seconds,
    )
    if result.get("success") is not True:
        raise HTTPException(status_code=_status_for(result), detail=result)
    try:
        _audit("queue.acknowledge", "completed", {"message_id": message_id, "success": request.success})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "queue_ack_audit_failed", "side_effect_may_have_occurred": True, "message_id": message_id},
        ) from exc
    return result


@router.post("/schedule/once", status_code=202)
def schedule_core_task(request: ScheduleOnceRequest):
    try:
        _audit("task.schedule", "requested", {
            "run_at": request.run_at,
            "task_sha256": hashlib.sha256(request.task.encode("utf-8")).hexdigest(),
        })
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Scheduling was blocked because the audit log is unavailable.") from exc
    result = TaskSchedulerService().schedule_once(
        request.task,
        request.run_at,
        owner_approved=request.owner_approved,
        metadata=request.metadata,
    )
    if result.get("success") is not True:
        raise HTTPException(status_code=_status_for(result), detail=result)
    job = result.get("job") or {}
    try:
        _audit("task.schedule", "completed", {
            "job_id": job.get("job_id"),
            "run_at": job.get("run_at"),
        })
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "schedule_audit_failed", "side_effect_may_have_occurred": True, "job_id": job.get("job_id")},
        ) from exc
    return result


@router.post("/schedule/interval", status_code=202)
def schedule_core_interval(request: ScheduleIntervalRequest):
    try:
        _audit("task.schedule_interval", "requested", {
            "first_run_at": request.first_run_at,
            "interval_seconds": request.interval_seconds,
            "max_runs": request.max_runs,
            "task_sha256": hashlib.sha256(request.task.encode("utf-8")).hexdigest(),
        })
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Recurring scheduling was blocked because the audit log is unavailable.") from exc
    result = TaskSchedulerService().schedule_interval(
        request.task,
        request.first_run_at,
        interval_seconds=request.interval_seconds,
        max_runs=request.max_runs,
        owner_approved=request.owner_approved,
        metadata=request.metadata,
    )
    if result.get("success") is not True:
        raise HTTPException(status_code=_status_for(result), detail=result)
    job = result.get("job") or {}
    try:
        _audit("task.schedule_interval", "completed", {
            "job_id": job.get("job_id"),
            "interval_seconds": request.interval_seconds,
            "max_runs": request.max_runs,
        })
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "recurring_schedule_audit_failed", "side_effect_may_have_occurred": True, "job_id": job.get("job_id")},
        ) from exc
    return result


@router.get("/schedule")
def list_core_schedules(status: str | None = None, limit: int = 100):
    result = TaskSchedulerService().list(status=status, limit=limit)
    if result.get("success") is not True:
        raise HTTPException(status_code=422 if result.get("code") in {"invalid_status", "invalid_limit"} else 503, detail=result)
    return result


@router.post("/schedule/claim-due")
def claim_due_core_schedules(limit: int = 1):
    try:
        _audit("task.claim_due", "requested", {"limit": limit})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Due-job claim was blocked because the audit log is unavailable.") from exc
    result = TaskSchedulerService().claim_due(limit=limit)
    if result.get("success") is not True:
        raise HTTPException(status_code=422 if result.get("code") == "invalid_limit" else 503, detail=result)
    jobs = result.get("jobs", [])
    try:
        _audit(
            "task.claim_due",
            "completed" if jobs else "empty",
            {"job_ids": [item.get("job_id") for item in jobs if isinstance(item, dict)]},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "schedule_claim_audit_failed", "side_effect_may_have_occurred": True},
        ) from exc
    return result


@router.post("/schedule/dispatch-due")
def dispatch_due_core_schedules(request: DispatchDueRequest, background_tasks: BackgroundTasks):
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    result = ScheduledTaskDispatchService().dispatch_due(limit=request.limit)
    if result.get("success") is not True:
        code = result.get("code")
        status = 403 if code in {"autonomous_permission_required", "autonomous_permission_state_unavailable"} or (isinstance(code, str) and code.startswith("autonomous_")) else 503 if code and ("unavailable" in code or "audit" in code) else 409
        raise HTTPException(status_code=status, detail=result)
    worker = BackgroundAgentWorkerService()
    for item in result.get("dispatched", []):
        task_id = item.get("background_task_id") if isinstance(item, dict) else None
        if isinstance(task_id, str):
            background_tasks.add_task(worker.execute, task_id)
    return result


@router.post("/schedule/sync-results")
def sync_core_schedule_results(request: SyncScheduleResultsRequest):
    result = ScheduledTaskDispatchService().sync_results(limit=request.limit)
    if result.get("success") is not True:
        raise HTTPException(status_code=503 if result.get("code", "").endswith("unavailable") else 409, detail=result)
    return result


@router.post("/schedule/{job_id}/finish")
def finish_core_schedule(job_id: str, request: ScheduleFinishRequest):
    try:
        _audit("task.finish", "requested", {"job_id": job_id, "success": request.success})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Job completion was blocked because the audit log is unavailable.") from exc
    result = TaskSchedulerService().finish(job_id, success=request.success, error=request.error)
    if result.get("success") is not True:
        raise HTTPException(status_code=_status_for(result), detail=result)
    try:
        _audit("task.finish", "completed", {"job_id": job_id, "success": request.success})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "schedule_finish_audit_failed", "side_effect_may_have_occurred": True, "job_id": job_id},
        ) from exc
    return result


@router.post("/schedule/{job_id}/cancel")
def cancel_core_schedule(job_id: str, request: ScheduleCancelRequest):
    if request.confirm is not True:
        raise HTTPException(status_code=409, detail="Explicit owner confirmation is required.")
    try:
        _audit("task.cancel", "requested", {"job_id": job_id})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Cancellation was blocked because the audit log is unavailable.") from exc
    result = TaskSchedulerService().cancel(job_id, owner_confirmed=request.confirm)
    if result.get("success") is not True:
        raise HTTPException(status_code=_status_for(result), detail=result)
    try:
        _audit("task.cancel", "completed", {"job_id": job_id})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "schedule_cancel_audit_failed", "side_effect_may_have_occurred": True},
        ) from exc
    return result
