from __future__ import annotations

from typing import Any

from app.services.autonomous_development.development_backlog_service import DevelopmentBacklogService


class DevelopmentTaskPlanner:
    """Turn verified audit findings into a small actionable roadmap."""

    MAX_TASKS = 5
    DEFAULT_VALIDATION = [["python", "-m", "pytest", "-q"]]

    def __init__(self, backlog: DevelopmentBacklogService | None = None) -> None:
        self.backlog = backlog or DevelopmentBacklogService()

    def plan(self, goal: str, audit: dict[str, Any]) -> list[dict[str, Any]]:
        findings = audit.get("findings", []) if isinstance(audit, dict) else []
        if not isinstance(findings, list):
            return []

        tasks = []
        seen = set()
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            objective = finding.get("objective")
            if not isinstance(objective, str) or not objective.strip():
                continue
            identity = (objective.casefold(), finding.get("path"))
            if identity in seen:
                continue
            seen.add(identity)
            evidence = finding.get("evidence")
            acceptance = finding.get("acceptance")
            files = []
            path = finding.get("path")
            if isinstance(path, str) and not path.startswith("recovery:"):
                files.append(path)
            task = {
                "objective": objective.strip(),
                "category": str(finding.get("category", "implementation")),
                "priority": int(finding.get("priority", 50)),
                "dependencies": [],
                "relevant_files": files[:12],
                "acceptance_criteria": [
                    str(acceptance or "Implement the verified behavior and add focused regression coverage."),
                    "Run the recorded validation command successfully.",
                    "Verify every modified file remains inside WorkspaceBoundary.",
                ],
                "validation_commands": self.DEFAULT_VALIDATION,
                "recovery_run_id": finding.get("recovery_run_id"),
                "source_workflow_id": finding.get("workflow_id"),
                "audit_evidence": evidence,
            }
            tasks.append(task)
            if len(tasks) >= self.MAX_TASKS:
                break
        return tasks

    def create_or_resume_program(
        self,
        goal: str,
        audit: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self.backlog.latest_program()
        if existing is not None:
            additions = self.plan(goal, audit)
            refreshed = self.backlog.update_audit(existing["program_id"], audit)
            return self.backlog.append_tasks(existing["program_id"], additions) if additions else refreshed
        tasks = self.plan(goal, audit)
        if not tasks:
            return self.backlog.create_program(
                goal,
                [],
                audit={**audit, "no_actionable_findings": True},
            )
        return self.backlog.create_program(goal, tasks, audit=audit)