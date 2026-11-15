"""Bridge approved one-shot schedules into Lumira's durable agent-task queue."""
from __future__ import annotations

from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
from app.services.background_tasks.background_agent_task_service import BackgroundAgentTaskService
from app.services.security.security_audit_log_service import SecurityAuditLogService
from app.services.system.task_scheduler_service import TaskSchedulerService


class ScheduledTaskDispatchService:
    """Dispatch due jobs only after autonomy permission and audit preflight."""

    def __init__(self, scheduler=None, background_tasks=None, autonomy=None, audit=None):
        self.scheduler = scheduler or TaskSchedulerService()
        self.background_tasks = background_tasks or BackgroundAgentTaskService()
        self.autonomy = autonomy or AutonomyPermissionService()
        self.audit = audit or SecurityAuditLogService()

    def sync_results(self, limit: int = 20) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            return {"success": False, "code": "invalid_limit", "synced": []}
        try:
            self.audit.append(
                event_type="scheduled_task_dispatch",
                action="task.sync_results",
                outcome="requested",
                actor="local_owner",
                details={"limit": limit},
            )
        except Exception:
            return {"success": False, "code": "security_audit_unavailable", "synced": []}
        scheduled = self.scheduler.list(status="dispatched", limit=limit)
        if scheduled.get("success") is not True:
            return {"success": False, "code": scheduled.get("code", "scheduler_unavailable"), "synced": []}
        synced = []
        pending = []
        for job in scheduled.get("jobs", []):
            task_id = job.get("background_task_id") if isinstance(job, dict) else None
            job_id = job.get("job_id") if isinstance(job, dict) else None
            task = self.background_tasks.get(task_id) if isinstance(task_id, str) else None
            if not isinstance(task, dict) or task.get("status") not in {"completed", "failed", "interrupted"}:
                pending.append(job_id)
                continue
            success = task.get("status") == "completed"
            result = self.scheduler.finish(
                job_id,
                success=success,
                error=task.get("error"),
            )
            if result.get("success") is True:
                synced.append({"job_id": job_id, "background_task_id": task_id, "status": result["job"]["status"]})
            else:
                pending.append(job_id)
        try:
            self.audit.append(
                event_type="scheduled_task_dispatch",
                action="task.sync_results",
                outcome="completed" if not pending else "partial",
                actor="local_owner",
                details={"synced_job_ids": [item["job_id"] for item in synced], "pending_count": len(pending)},
            )
        except Exception:
            return {
                "success": False,
                "code": "sync_outcome_audit_failed",
                "synced": synced,
                "pending_job_ids": pending,
                "side_effect_may_have_occurred": bool(synced),
            }
        return {"success": not pending, "synced": synced, "pending_job_ids": pending}

    def dispatch_due(self, limit: int = 1) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5:
            return {"success": False, "code": "invalid_limit", "dispatched": []}
        try:
            authorization = self.autonomy.authorize("agent.dispatch", autonomous=True)
        except Exception:
            return {"success": False, "code": "autonomy_permission_state_unavailable", "dispatched": []}
        if not isinstance(authorization, dict) or authorization.get("allowed") is not True:
            code = authorization.get("code", "autonomous_permission_required") if isinstance(authorization, dict) else "autonomous_permission_required"
            return {"success": False, "code": code, "authorization": authorization, "dispatched": []}
        try:
            self.audit.append(
                event_type="scheduled_task_dispatch",
                action="task.dispatch_due",
                outcome="requested",
                actor="local_owner",
                details={"limit": limit},
            )
        except Exception:
            return {"success": False, "code": "security_audit_unavailable", "dispatched": []}

        claimed = self.scheduler.claim_due(limit=limit)
        if claimed.get("success") is not True:
            return {"success": False, "code": claimed.get("code", "scheduler_unavailable"), "dispatched": []}

        dispatched = []
        failures = []
        for job in claimed.get("jobs", []):
            if not isinstance(job, dict):
                continue
            job_id = job.get("job_id")
            task = job.get("task")
            if not isinstance(job_id, str) or not isinstance(task, str):
                failures.append({"job_id": job_id, "code": "invalid_claimed_job"})
                continue
            recurrence = job.get("recurrence")
            occurrence = recurrence.get("run_count", 1) if isinstance(recurrence, dict) else 1
            if isinstance(occurrence, bool) or not isinstance(occurrence, int) or occurrence < 1:
                self.scheduler.finish(job_id, success=False, error="invalid_schedule_occurrence")
                failures.append({"job_id": job_id, "code": "invalid_schedule_occurrence"})
                continue
            created = self.background_tasks.create(
                task,
                autonomous=True,
                idempotency_key=f"schedule:{job_id}:run:{occurrence}",
            )
            if created.get("success") is not True:
                self.scheduler.finish(job_id, success=False, error=str(created.get("code", "background_task_creation_failed")))
                failures.append({"job_id": job_id, "code": created.get("code", "background_task_creation_failed")})
                continue
            background = created.get("task")
            background_id = background.get("task_id") if isinstance(background, dict) else None
            if not isinstance(background_id, str) or not background_id:
                self.scheduler.finish(job_id, success=False, error="background_task_id_missing")
                failures.append({"job_id": job_id, "code": "background_task_id_missing"})
                continue
            linked = self.scheduler.mark_dispatched(job_id, background_id)
            if linked.get("success") is not True:
                failures.append({
                    "job_id": job_id,
                    "background_task_id": background_id,
                    "code": linked.get("code", "scheduler_link_failed"),
                    "side_effect_may_have_occurred": True,
                })
                continue
            dispatched.append({
                "job_id": job_id,
                "background_task_id": background_id,
                "status": "queued_for_agent_worker",
            })

        try:
            self.audit.append(
                event_type="scheduled_task_dispatch",
                action="task.dispatch_due",
                outcome="completed" if not failures else "partial",
                actor="local_owner",
                details={
                    "dispatched_job_ids": [item["job_id"] for item in dispatched],
                    "failure_count": len(failures),
                },
            )
        except Exception:
            return {
                "success": False,
                "code": "dispatch_outcome_audit_failed",
                "dispatched": dispatched,
                "failures": failures,
                "side_effect_may_have_occurred": bool(dispatched or failures),
            }
        return {
            "success": not failures,
            "dispatched": dispatched,
            "failures": failures,
            "claimed_count": len(claimed.get("jobs", [])),
            "message": "Scheduled tasks are queued for the existing agent worker; this operation does not execute them inline.",
        }
