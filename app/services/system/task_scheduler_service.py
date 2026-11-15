"""Durable one-shot task scheduler; due jobs run only when an owner worker claims them."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError
from app.services.sessions.session_manager_service import redact_sensitive_text, redact_sensitive_value


class TaskSchedulerService:
    MAX_JOBS = 1000
    MAX_TASK_CHARS = 10000
    CLAIM_LEASE_SECONDS = 300
    STATUSES = {"scheduled", "claimed", "dispatched", "completed", "cancelled", "failed"}

    def __init__(self, storage_path: str = "memory/scheduled_tasks.json"):
        self.store = AtomicJsonStore(storage_path)
        self.store.read_or_create({"schema_version": 1, "jobs": []})
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _validate(cls, document: Any) -> list[dict]:
        if not isinstance(document, dict) or document.get("schema_version") != 1:
            raise PersistenceIntegrityError("scheduler schema is invalid")
        jobs = document.get("jobs")
        if not isinstance(jobs, list) or len(jobs) > cls.MAX_JOBS:
            raise PersistenceIntegrityError("scheduler jobs are invalid")
        ids = set()
        for item in jobs:
            if not isinstance(item, dict):
                raise PersistenceIntegrityError("scheduler record is invalid")
            job_id = item.get("job_id")
            if not isinstance(job_id, str) or not job_id or job_id in ids:
                raise PersistenceIntegrityError("scheduler job identity is invalid")
            ids.add(job_id)
            recurrence = item.get("recurrence")
            if recurrence is not None and (
                not isinstance(recurrence, dict)
                or set(recurrence) != {"interval_seconds", "max_runs", "run_count", "skipped_count"}
                or any(isinstance(recurrence.get(key), bool) or not isinstance(recurrence.get(key), int) for key in recurrence)
                or not 60 <= recurrence["interval_seconds"] <= 31_536_000
                or not 1 <= recurrence["max_runs"] <= 1000
                or not 0 <= recurrence["run_count"] <= recurrence["max_runs"]
                or not 0 <= recurrence["skipped_count"] <= 1_000_000
            ):
                raise PersistenceIntegrityError("scheduler recurrence is invalid")
            if (
                not isinstance(item.get("status"), str)
                or item["status"] not in cls.STATUSES
                or not isinstance(item.get("task"), str)
                or not item["task"].strip()
                or len(item["task"]) > cls.MAX_TASK_CHARS
                or item.get("owner_approved") is not True
                or not isinstance(item.get("metadata"), dict)
                or (item.get("status") == "dispatched" and (not isinstance(item.get("background_task_id"), str) or not item.get("background_task_id")))
            ):
                raise PersistenceIntegrityError("scheduler job fields are invalid")
        return jobs

    def schedule_once(self, task: str, run_at: str, *, owner_approved: bool = False, metadata: dict | None = None, recurrence: dict | None = None) -> dict:
        if not isinstance(task, str) or not task.strip() or len(task) > self.MAX_TASK_CHARS:
            return {"success": False, "code": "invalid_task"}
        if owner_approved is not True:
            return {"success": False, "code": "explicit_owner_approval_required"}
        if not isinstance(run_at, str) or len(run_at) > 64:
            return {"success": False, "code": "invalid_run_at"}
        try:
            due = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
            if due.tzinfo is None:
                return {"success": False, "code": "timezone_required"}
            due = due.astimezone(timezone.utc)
        except ValueError:
            return {"success": False, "code": "invalid_run_at"}
        if due <= self._now():
            return {"success": False, "code": "run_at_must_be_future"}
        if metadata is not None and not isinstance(metadata, dict):
            return {"success": False, "code": "invalid_metadata"}
        normalized_recurrence = None
        if recurrence is not None:
            if not isinstance(recurrence, dict) or set(recurrence) != {"interval_seconds", "max_runs"}:
                return {"success": False, "code": "invalid_recurrence"}
            interval = recurrence.get("interval_seconds")
            max_runs = recurrence.get("max_runs")
            if (
                isinstance(interval, bool) or not isinstance(interval, int)
                or not 60 <= interval <= 31_536_000
                or isinstance(max_runs, bool) or not isinstance(max_runs, int)
                or not 1 <= max_runs <= 1000
            ):
                return {"success": False, "code": "invalid_recurrence"}
            normalized_recurrence = {
                "interval_seconds": interval,
                "max_runs": max_runs,
                "run_count": 0,
                "skipped_count": 0,
            }
        safe_task = redact_sensitive_text(task.strip())
        safe_metadata = redact_sensitive_value(metadata or {})
        if not safe_task or not isinstance(safe_metadata, dict):
            return {"success": False, "code": "invalid_task_or_metadata_after_redaction"}
        try:
            import json
            if len(json.dumps(safe_metadata, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 32_768:
                return {"success": False, "code": "metadata_too_large"}
        except (TypeError, ValueError, RecursionError):
            return {"success": False, "code": "metadata_not_json"}
        job = {
            "job_id": str(uuid4()), "task": safe_task, "run_at": due.isoformat(),
            "status": "scheduled", "owner_approved": True,
            "metadata": safe_metadata, "created_at": self._now().isoformat(),
            "updated_at": self._now().isoformat(), "claimed_at": None,
            **({"recurrence": normalized_recurrence} if normalized_recurrence is not None else {}),
        }
        def insert(document):
            jobs = self._validate(document)
            if len(jobs) >= self.MAX_JOBS:
                terminal = next((i for i, item in enumerate(jobs) if item["status"] in {"completed", "cancelled", "failed"}), None)
                if terminal is None:
                    return {"error": "scheduler_capacity_reached"}
                jobs.pop(terminal)
            jobs.append(job)
            return dict(job)
        try:
            result = self.store.update(insert, {"schema_version": 1, "jobs": []})
        except Exception:
            return {"success": False, "code": "scheduler_storage_unavailable"}
        return {"success": "error" not in result, "job": result if "error" not in result else None, "code": result.get("error")}

    def schedule_interval(
        self,
        task: str,
        first_run_at: str,
        *,
        interval_seconds: int,
        max_runs: int,
        owner_approved: bool = False,
        metadata: dict | None = None,
    ) -> dict:
        """Create a bounded fixed-interval schedule; each run still needs dispatch."""
        return self.schedule_once(
            task,
            first_run_at,
            owner_approved=owner_approved,
            metadata=metadata,
            recurrence={"interval_seconds": interval_seconds, "max_runs": max_runs},
        )

    def claim_due(self, limit: int = 1) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
            return {"success": False, "code": "invalid_limit", "jobs": []}
        now = self._now()
        def claim(document):
            jobs = self._validate(document)
            # Recover a worker claim abandoned by a process restart.
            for job in jobs:
                if job["status"] == "claimed":
                    try:
                        stale = datetime.fromisoformat(job["claimed_at"]) + timedelta(seconds=self.CLAIM_LEASE_SECONDS) <= now
                    except (TypeError, ValueError):
                        stale = True
                    if stale:
                        job["status"] = "scheduled"
                        job["claimed_at"] = None
                        job["updated_at"] = now.isoformat()
                        job["last_recovery"] = "claim_lease_expired"
            due = []
            for job in jobs:
                if job["status"] != "scheduled":
                    continue
                try:
                    ready = datetime.fromisoformat(job["run_at"]) <= now
                except (TypeError, ValueError):
                    ready = False
                if ready and job.get("owner_approved") is True:
                    job["status"] = "claimed"
                    job["claimed_at"] = now.isoformat()
                    recurrence = job.get("recurrence")
                    if isinstance(recurrence, dict):
                        recurrence["run_count"] += 1
                    job["updated_at"] = now.isoformat()
                    due.append(dict(job))
                    if len(due) >= limit:
                        break
            return due
        try:
            jobs = self.store.update(claim, {"schema_version": 1, "jobs": []})
        except Exception:
            return {"success": False, "code": "scheduler_storage_unavailable", "jobs": []}
        return {"success": True, "jobs": jobs, "count": len(jobs)}

    def mark_dispatched(self, job_id: str, background_task_id: str) -> dict:
        if (
            not isinstance(job_id, str) or not job_id
            or not isinstance(background_task_id, str) or not background_task_id
            or len(background_task_id) > 128
        ):
            return {"success": False, "code": "invalid_dispatch_reference"}

        def update(document):
            jobs = self._validate(document)
            job = next((item for item in jobs if item["job_id"] == job_id), None)
            if job is None:
                return {"error": "job_not_found"}
            if job["status"] != "claimed":
                return {"error": "job_not_claimed"}
            job["status"] = "dispatched"
            job["background_task_id"] = background_task_id
            job["updated_at"] = self._now().isoformat()
            return dict(job)

        try:
            result = self.store.update(update, {"schema_version": 1, "jobs": []})
        except Exception:
            return {"success": False, "code": "scheduler_storage_unavailable"}
        return {"success": "error" not in result, "job": result if "error" not in result else None, "code": result.get("error")}

    def finish(self, job_id: str, *, success: bool, error: str | None = None) -> dict:
        if not isinstance(job_id, str) or not job_id or not isinstance(success, bool):
            return {"success": False, "code": "invalid_result"}
        def update(document):
            jobs = self._validate(document)
            job = next((item for item in jobs if item["job_id"] == job_id), None)
            if job is None:
                return {"error": "job_not_found"}
            if job["status"] not in {"claimed", "dispatched"}:
                return {"error": "job_not_claimed_or_dispatched"}
            now = self._now()
            recurrence = job.get("recurrence")
            if success and isinstance(recurrence, dict) and recurrence["run_count"] < recurrence["max_runs"]:
                interval = recurrence["interval_seconds"]
                previous_due = datetime.fromisoformat(job["run_at"])
                next_due = previous_due + timedelta(seconds=interval)
                skipped = 0
                if next_due <= now:
                    skipped = int((now - next_due).total_seconds() // interval) + 1
                    next_due += timedelta(seconds=skipped * interval)
                recurrence["skipped_count"] = min(1_000_000, recurrence["skipped_count"] + skipped)
                job["run_at"] = next_due.astimezone(timezone.utc).isoformat()
                job["status"] = "scheduled"
                job["claimed_at"] = None
                job["background_task_id"] = None
                job["last_completed_at"] = now.isoformat()
                job["last_error"] = None
            else:
                job["status"] = "completed" if success else "failed"
                job["error"] = str(error)[:500] if error else None
                job["completed_at"] = now.isoformat()
            job["updated_at"] = now.isoformat()
            return dict(job)
        try:
            result = self.store.update(update, {"schema_version": 1, "jobs": []})
        except Exception:
            return {"success": False, "code": "scheduler_storage_unavailable"}
        return {"success": "error" not in result, "job": result if "error" not in result else None, "code": result.get("error")}

    def cancel(self, job_id: str, *, owner_confirmed: bool) -> dict:
        if owner_confirmed is not True:
            return {"success": False, "code": "explicit_owner_confirmation_required"}
        def update(document):
            jobs = self._validate(document)
            job = next((item for item in jobs if item["job_id"] == job_id), None)
            if job is None:
                return {"error": "job_not_found"}
            if job["status"] != "scheduled":
                return {"error": "job_not_cancellable"}
            job["status"] = "cancelled"
            job["updated_at"] = self._now().isoformat()
            return dict(job)
        try:
            result = self.store.update(update, {"schema_version": 1, "jobs": []})
        except Exception:
            return {"success": False, "code": "scheduler_storage_unavailable"}
        return {"success": "error" not in result, "job": result if "error" not in result else None, "code": result.get("error")}

    def list(self, status: str | None = None, limit: int = 100) -> dict:
        if status is not None and status not in self.STATUSES:
            return {"success": False, "code": "invalid_status", "jobs": []}
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            return {"success": False, "code": "invalid_limit", "jobs": []}
        try:
            jobs = list(self._validate(self.store.read({"schema_version": 1, "jobs": []})))
        except Exception:
            return {"success": False, "code": "scheduler_storage_unavailable", "jobs": []}
        filtered = [item for item in jobs if status is None or item["status"] == status]
        return {"success": True, "jobs": filtered[-limit:], "count": len(filtered)}
