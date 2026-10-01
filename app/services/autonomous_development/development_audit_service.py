from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.autonomous_development.worker.development_worker import DevelopmentWorker
from app.services.workflow_recovery.run_recovery_service import RunRecoveryService
from app.services.work_items.work_item_service import WorkItemService


class DevelopmentAuditService:
    """Collect bounded repository evidence and recoverable development runs."""

    MAX_RECOVERY_CANDIDATES = 5

    def __init__(
        self,
        worker: DevelopmentWorker,
        *,
        work_items: WorkItemService | None = None,
        recovery: RunRecoveryService | None = None,
    ) -> None:
        self.worker = worker
        self.work_items = work_items or WorkItemService()
        self.recovery = recovery or RunRecoveryService()

    def run(self) -> dict[str, Any]:
        inspection = self.worker.inspect()
        findings = list(inspection.get("audit_findings", []))
        existing_keys = {(item.get("path"), item.get("objective")) for item in findings if isinstance(item, dict)}

        runs_by_workflow = {}
        for run in self.recovery.list_runs(limit=100):
            if not isinstance(run, dict):
                continue
            plan = run.get("plan", {})
            if isinstance(plan, dict) and plan.get("autonomous_development"):
                runs_by_workflow[plan.get("workflow_id")] = run

        for workflow in self.work_items.list_workflows(category="operations", limit=200):
            if workflow.get("title") not in {
                "Autonomous Lumira Development",
                "Bounded Lumira completion workflow",
            }:
                continue
            if workflow.get("status") not in {"failed", "blocked", "in_progress"}:
                continue
            run = runs_by_workflow.get(workflow.get("workflow_id"))
            if not run or not run.get("resume_allowed"):
                continue
            task = next(
                (item for item in workflow.get("tasks", []) if item.get("status") in {"failed", "in_progress", "blocked"}),
                None,
            )
            objective = workflow.get("request", "").strip()
            key = ("recovery", objective)
            if not objective or key in existing_keys:
                continue
            findings.append({
                "path": "recovery:" + str(run["run_id"]),
                "objective": objective,
                "acceptance": "Resume from the persisted safe checkpoint, validate the applied state, and complete or persist a specific blocker.",
                "evidence": {
                    "workflow_id": workflow["workflow_id"],
                    "recovery_run_id": run["run_id"],
                    "workflow_status": workflow["status"],
                    "failed_task": task.get("title") if task else None,
                    "failed_stage": run.get("current_stage"),
                    "safe_resume_point": run.get("safe_resume_point"),
                    "last_error": run.get("error"),
                },
                "recovery_run_id": run["run_id"],
                "workflow_id": workflow["workflow_id"],
                "category": "recovery",
                "priority": 90,
            })
            existing_keys.add(key)
            if len(findings) >= self.worker.MAX_AUDIT_FINDINGS + self.MAX_RECOVERY_CANDIDATES:
                break

        return {
            "workspace": ".",
            "file_count": inspection["file_count"],
            "findings": findings,
            "audited_at": datetime.now(UTC).isoformat(),
            "completion_ready": False,
            "completion_blockers": [
                "This bounded self-development audit currently checks source TODO/FIXME evidence and recoverable autonomous runs; it is not yet a verified whole-Lumira subsystem/integration audit.",
                "A final program-completion audit must cover backend routes, services, desktop contracts, persistence, voice, artifacts, search, modes, sessions, and security.",
            ],
            "limits": {
                "max_source_files": self.worker.MAX_AUDIT_FILES,
                "max_source_chars": self.worker.MAX_AUDIT_SOURCE_CHARS,
                "max_findings": self.worker.MAX_AUDIT_FINDINGS + self.MAX_RECOVERY_CANDIDATES,
            },
        }