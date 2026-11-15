"""Resource-aware worker boundary for durable background-agent tasks."""
from __future__ import annotations

from app.services.background_tasks.background_agent_task_service import BackgroundAgentTaskService
from app.services.security.security_audit_log_service import SecurityAuditLogService
from app.services.system.agent_execution_lease_service import AgentExecutionLeaseService
from app.services.system.task_scheduler_service import TaskSchedulerService


class BackgroundAgentWorkerService:
    """Acquire a shared RAM-aware lease before claiming and executing an agent task."""

    def __init__(self, task_service=None, lease_service=None, scheduler=None, audit=None):
        self.tasks = task_service or BackgroundAgentTaskService()
        self.leases = lease_service or AgentExecutionLeaseService()
        self.scheduler = scheduler or TaskSchedulerService()
        self.audit = audit or SecurityAuditLogService()

    def _sync_scheduled_job(self, task: dict, succeeded: bool) -> dict | None:
        key = task.get("idempotency_key")
        if not isinstance(key, str) or not key.startswith("schedule:"):
            return None
        parts = key.split(":")
        if len(parts) == 2:
            job_id = parts[1]  # Backward-compatible one-shot key.
        elif len(parts) == 4 and parts[2] == "run" and parts[3].isdigit():
            job_id = parts[1]  # Unique per-occurrence idempotency key.
        else:
            return {"success": False, "code": "invalid_schedule_idempotency_key"}
        if not job_id:
            return {"success": False, "code": "invalid_schedule_idempotency_key"}
        try:
            self.audit.append(
                event_type="scheduled_task_dispatch",
                action="task.worker_finish",
                outcome="requested",
                actor="local_owner",
                details={"job_id": job_id, "background_task_id": task.get("task_id")},
            )
        except Exception:
            return {
                "success": False,
                "code": "schedule_finish_audit_unavailable",
                "side_effect_may_have_occurred": True,
            }
        result = self.scheduler.finish(
            job_id,
            success=succeeded,
            error=task.get("error"),
        )
        if result.get("success") is not True:
            # A prior explicit sync may already have finalized the schedule.
            if result.get("code") == "job_not_claimed_or_dispatched":
                return {"success": True, "status": "already_finalized"}
            return {"success": False, "code": result.get("code", "schedule_finish_failed")}
        try:
            self.audit.append(
                event_type="scheduled_task_dispatch",
                action="task.worker_finish",
                outcome="completed",
                actor="local_owner",
                details={
                    "job_id": job_id,
                    "background_task_id": task.get("task_id"),
                    "schedule_status": result.get("job", {}).get("status"),
                },
            )
        except Exception:
            return {
                "success": False,
                "code": "schedule_finish_outcome_audit_failed",
                "side_effect_may_have_occurred": True,
            }
        return {"success": True, "status": result.get("job", {}).get("status")}

    def execute(self, task_id: str) -> dict:
        acquired = self.leases.acquire(task_id)
        if acquired.get("success") is not True:
            return {
                "success": False,
                "code": acquired.get("code", "execution_budget_unavailable"),
                "task_id": task_id,
                "retry_after_seconds": acquired.get("retry_after_seconds", 30),
            }
        lease_id = acquired["lease"]["lease_id"]
        try:
            outcome = self.tasks.execute(task_id)
            task = outcome.get("task") if isinstance(outcome, dict) else None
            if isinstance(task, dict):
                schedule = self._sync_scheduled_job(task, outcome.get("success") is True)
                if schedule is not None:
                    outcome["schedule"] = schedule
                    if schedule.get("success") is not True:
                        outcome["side_effect_may_have_occurred"] = True
            return outcome
        finally:
            self.leases.release(lease_id)
