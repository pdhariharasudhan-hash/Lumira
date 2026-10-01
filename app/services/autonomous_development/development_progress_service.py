from __future__ import annotations

from typing import Any

from app.services.autonomous_development.development_backlog_service import DevelopmentBacklogService


class DevelopmentProgressService:
    """Persist meaningful development-task transitions and lessons."""

    def __init__(self, backlog: DevelopmentBacklogService | None = None) -> None:
        self.backlog = backlog or DevelopmentBacklogService()

    def start(self, program_id: str, task_id: str, *, iteration: int) -> dict[str, Any]:
        task = self.backlog.get_program(program_id)
        if task is None:
            raise KeyError("development program not found")
        record = next((item for item in task["tasks"] if item["task_id"] == task_id), None)
        if record is None:
            raise KeyError("development task not found")
        if record["attempts"] >= self.backlog.MAX_ATTEMPTS:
            return self.backlog.update_task(
                program_id,
                task_id,
                status="blocked",
                last_error={"code": "attempt_limit_reached", "message": "Bounded task attempts exhausted."},
            )
        return self.backlog.update_task(
            program_id,
            task_id,
            status="in_progress",
            attempts=record["attempts"] + 1,
            iteration=max(1, iteration),
            last_error=None,
        )

    def checkpoint(
        self,
        program_id: str,
        task_id: str,
        *,
        iteration: int,
        recovery_run_id: str | None = None,
        validation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {"iteration": max(0, iteration)}
        if recovery_run_id is not None:
            updates["recovery_run_id"] = recovery_run_id
        if validation is not None:
            updates["last_validation"] = self.summarize_validation(validation)
        return self.backlog.update_task(program_id, task_id, **updates)

    def complete(
        self,
        program_id: str,
        task_id: str,
        *,
        result: dict[str, Any],
        validation: dict[str, Any],
    ) -> dict[str, Any]:
        if validation.get("return_code") != 0 or validation.get("status") != "completed":
            raise ValueError("A development task cannot complete without successful validation")
        task = self.backlog.update_task(
            program_id,
            task_id,
            status="completed",
            last_validation=self.summarize_validation(validation),
            last_error=None,
        )
        self.backlog.add_lesson({
            "program_id": program_id,
            "task_id": task_id,
            "objective": task["objective"],
            "changes": result.get("files_changed", []),
            "tests": validation.get("command", []),
            "validation_status": validation.get("status"),
            "provider": result.get("provider"),
            "lessons": result.get("lessons", []),
        })
        return task

    def fail_or_block(
        self,
        program_id: str,
        task_id: str,
        *,
        error: dict[str, Any],
        validation: dict[str, Any] | None = None,
        retryable: bool,
    ) -> dict[str, Any]:
        program = self.backlog.get_program(program_id)
        task = next(item for item in program["tasks"] if item["task_id"] == task_id)
        exhausted = task["attempts"] >= self.backlog.MAX_ATTEMPTS
        state = "planned" if retryable and not exhausted else "blocked"
        diagnosed = self.diagnose_failure(error, validation)
        safe_error = {**error, **diagnosed}
        updated = self.backlog.update_task(
            program_id,
            task_id,
            status=state,
            last_error=safe_error,
            last_validation=self.summarize_validation(validation) if validation else None,
        )
        self.backlog.add_lesson({
            "program_id": program_id,
            "task_id": task_id,
            "objective": task["objective"],
            "failure_code": error.get("code"),
            "failure_category": diagnosed["category"],
            "validation_status": (validation or {}).get("status"),
            "recommended_next_action": diagnosed["recommended_next_action"],
        })
        return updated

    @staticmethod
    def summarize_validation(validation: dict[str, Any]) -> dict[str, Any]:
        output = str(validation.get("output", ""))
        return {
            "iteration": validation.get("iteration"),
            "status": validation.get("status"),
            "command": validation.get("command", []),
            "return_code": validation.get("return_code"),
            "output_tail": output[-4_000:],
            "output_truncated": len(output) > 4_000,
        }

    @staticmethod
    def diagnose_failure(
        error: dict[str, Any],
        validation: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        code = str(error.get("code", "")).casefold()
        message = str(error.get("message", "")).casefold()
        if code.startswith("provider_") or code == "provider_failover_exhausted":
            category = "provider_failure"
            next_action = "Check configured provider availability and resume the same generation checkpoint."
        elif "invalid_changes" in code or "malformed" in code or "old_content" in message:
            category = "malformed_or_stale_change"
            next_action = "Refresh relevant source context and regenerate exact old_content before applying."
        elif validation and validation.get("return_code") not in (None, 0):
            category = "test_failure"
            next_action = "Use the persisted validation output to diagnose, apply one bounded fix, and revalidate."
        elif "validation" in code or "test" in code:
            category = "validation_failure"
            next_action = "Inspect the validation checkpoint and retry only after a targeted fix."
        elif "dependency" in message or "import" in message:
            category = "dependency_problem"
            next_action = "Confirm the dependency is declared and available before another implementation attempt."
        elif "timeout" in code or "unreachable" in code or "connection" in message:
            category = "environment_problem"
            next_action = "Check local service/process availability; do not change source until the environment recovers."
        elif "resume_limit" in code or "attempt_limit" in code:
            category = "recovery_limit"
            next_action = "Preserve the checkpoint and reconcile or explicitly authorize a new bounded recovery window."
        elif "unsupported" in code:
            category = "unsupported_task"
            next_action = "Block this task with its capability limitation and select independent work."
        elif "unsafe" in code or "boundary" in code or "command" in code:
            category = "safety_rejection"
            next_action = "Do not weaken safety limits; revise the task to fit authorized workspace and commands."
        else:
            category = "implementation_failure"
            next_action = "Inspect the persisted error and relevant files before a bounded retry."
        return {"category": category, "recommended_next_action": next_action}