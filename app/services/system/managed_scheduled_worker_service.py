"""Opt-in lifecycle worker for explicitly owner-approved scheduled agent tasks."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.services.background_tasks.background_agent_task_service import BackgroundAgentTaskService
from app.services.background_tasks.background_agent_worker_service import BackgroundAgentWorkerService
from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
from app.services.system.scheduled_task_dispatch_service import ScheduledTaskDispatchService
from app.services.system.task_scheduler_service import TaskSchedulerService

logger = logging.getLogger(__name__)


class ManagedScheduledWorkerService:
    """Dispatch and execute approved schedules with bounded, graceful lifecycle."""

    MIN_INTERVAL_SECONDS = 5
    MAX_INTERVAL_SECONDS = 300

    def __init__(self, *, dispatcher=None, scheduler=None, tasks=None, worker=None, interval_seconds: int | None = None):
        self.scheduler = scheduler or TaskSchedulerService()
        self.tasks = tasks or BackgroundAgentTaskService()
        self.dispatcher = dispatcher or ScheduledTaskDispatchService(
            scheduler=self.scheduler, background_tasks=self.tasks
        )
        self.worker = worker or BackgroundAgentWorkerService(
            task_service=self.tasks, scheduler=self.scheduler
        )
        self.autonomy = AutonomyPermissionService()
        raw_interval = interval_seconds
        if raw_interval is None:
            try:
                raw_interval = int(os.getenv("LUMIRA_SCHEDULED_WORKER_INTERVAL_SECONDS", "15"))
            except (TypeError, ValueError):
                raw_interval = 15
        if isinstance(raw_interval, bool) or not isinstance(raw_interval, int):
            raw_interval = 15
        self.interval_seconds = max(self.MIN_INTERVAL_SECONDS, min(self.MAX_INTERVAL_SECONDS, raw_interval))
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._last_cycle: dict[str, Any] = {"status": "not_started"}

    @staticmethod
    def enabled() -> bool:
        return os.getenv("LUMIRA_SCHEDULED_WORKER_ENABLED", "").strip().lower() == "true"

    async def start(self) -> None:
        if not self.enabled():
            self._last_cycle = {"status": "disabled"}
            return
        if self._task is not None and not self._task.done():
            return
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="lumira-managed-scheduled-worker")
        self._last_cycle = {"status": "running", "interval_seconds": self.interval_seconds}

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._stop.set()
        try:
            # Shield the lifecycle task: cancelling asyncio.to_thread does not stop
            # its underlying worker thread and could falsely report a clean shutdown.
            await asyncio.wait_for(asyncio.shield(task), timeout=35)
        except asyncio.TimeoutError:
            self._last_cycle = {
                "status": "stop_requested",
                "active_cycle_may_still_be_finishing": True,
            }
            return
        finally:
            if task.done() and self._task is task:
                self._task = None
        self._last_cycle = {"status": "stopped"}

    def snapshot(self) -> dict[str, Any]:
        return {
            **self._last_cycle,
            "enabled": self.enabled(),
            "interval_seconds": self.interval_seconds,
            "task_running": self._task is not None and not self._task.done(),
            "execution_mode": "owner_approved_and_autonomy_permission_gated",
            "max_concurrent_tasks": 1,
        }

    def _cycle(self) -> dict[str, Any]:
        """Execute only task IDs linked from dispatched scheduler records."""
        dispatch = self.dispatcher.dispatch_due(limit=1)
        listed = self.scheduler.list(status="dispatched", limit=100)
        if listed.get("success") is not True:
            return {"status": "scheduler_unavailable", "dispatch_code": dispatch.get("code"), "scheduler_code": listed.get("code")}
        for job in listed.get("jobs", []):
            if not isinstance(job, dict):
                continue
            task_id = job.get("background_task_id")
            if not isinstance(task_id, str):
                continue
            task = self.tasks.get(task_id)
            if not isinstance(task, dict) or task.get("status") != "queued":
                continue
            # Re-check permission at execution time, not only at dispatch time.
            try:
                authorization = self.autonomy.authorize("agent.dispatch", autonomous=True)
            except Exception:
                return {"status": "autonomy_permission_state_unavailable", "job_id": job.get("job_id")}
            if not isinstance(authorization, dict) or authorization.get("allowed") is not True:
                return {
                    "status": "autonomy_permission_revoked_or_missing",
                    "job_id": job.get("job_id"),
                    "authorization_code": authorization.get("code") if isinstance(authorization, dict) else None,
                }
            outcome = self.worker.execute(task_id)
            return {
                "status": "task_processed" if outcome.get("success") else "task_deferred_or_failed",
                "job_id": job.get("job_id"),
                "task_id": task_id,
                "worker_code": outcome.get("code"),
                "task_status": (outcome.get("task") or {}).get("status") if isinstance(outcome.get("task"), dict) else None,
                "dispatch_status": dispatch.get("code", "ok"),
            }
        return {"status": "idle", "dispatched_count": len(dispatch.get("dispatched", [])), "dispatch_code": dispatch.get("code")}

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                result = await asyncio.to_thread(self._cycle)
                self._last_cycle = {"status": "running", "last_cycle": result}
                if result.get("status") == "scheduler_unavailable":
                    logger.warning("Scheduled worker cycle deferred: scheduler unavailable")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Scheduled worker cycle failed (%s)", type(exc).__name__)
                self._last_cycle = {"status": "running", "last_error_type": type(exc).__name__}
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass
