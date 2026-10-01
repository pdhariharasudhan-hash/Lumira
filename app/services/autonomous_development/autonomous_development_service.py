from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.agents.workflow_engine import WorkflowEngine
from app.services.workflow_recovery.run_recovery_service import RunRecoveryService
from app.services.work_items.work_item_service import WorkItemService

from app.services.autonomous_development.autonomous_development_loop import (
    AutonomousDevelopmentLoop,
)


class AutonomousDevelopmentService:
    """
    Durable autonomous development coordinator.

    Coordinates Lumira's existing:
        WorkItemService
        WorkflowEngine
        RunRecoveryService

    Development-specific work is routed through:
        AutonomousDevelopmentLoop

    The general WorkflowEngine remains available for existing
    Lumira workflows but is not used to reinterpret autonomous
    development tasks as generic capabilities.
    """

    MAX_TASKS = 12
    MAX_GOAL_LENGTH = 10_000
    MAX_STORED_RESULT_LENGTH = 3_900
    STALE_WORKFLOW_AFTER_SECONDS = 3_600

    def __init__(
        self,
        workspace: str | Path = ".",
        workflow_engine: WorkflowEngine | None = None,
        work_items: WorkItemService | None = None,
        recovery: RunRecoveryService | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()

        self.workflow_engine = (
            workflow_engine
            or WorkflowEngine()
        )

        self.work_items = (
            work_items
            or WorkItemService()
        )

        self.recovery = (
            recovery
            or RunRecoveryService()
        )

        self.development_loop = AutonomousDevelopmentLoop(
            self.workspace
        )

    def create_development_workflow(
        self,
        goal: str,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
        goal_id: str | None = None,
    ) -> dict[str, Any]:
        goal = self._validate_goal(goal)

        tasks = [
            "Inspect the Lumira workspace and determine the remaining development work.",
            "Create a bounded implementation plan from the inspected workspace.",
            "Implement the highest-priority development changes.",
            "Run the relevant backend and desktop validation.",
            "Diagnose any validation failures.",
            "Apply only bounded fixes for diagnosed failures.",
            "Re-run validation after fixes.",
            "Verify the completed work against the original development goal.",
            "Record the completed development result.",
        ]

        workflow = self.work_items.create_workflow(
            category="operations",
            title="Autonomous Lumira Development",
            request=goal,
            tasks=tasks,
            session_id=session_id,
            project_id=project_id,
            goal_id=goal_id,
        )

        return {
            "success": True,
            "workflow_id": workflow["workflow_id"],
            "goal": goal,
            "workspace": str(self.workspace),
            "tasks": workflow["tasks"],
        }

    def execute(
        self,
        goal: str,
        *,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a bounded autonomous development workflow.

        The workflow is durable at the WorkItemService level while the
        development loop performs bounded inspect -> plan -> generate ->
        apply -> validate -> fix/retest -> verify execution.
        """
        goal = self._validate_goal(goal)
        self._recover_stale_workflows()

        workflow = self.create_development_workflow(
            goal,
            session_id=session_id,
        )

        workflow_id = workflow["workflow_id"]
        tasks = workflow["tasks"]

        context: dict[str, Any] = {
            "goal": goal,
            "session_id": session_id,
        }

        completed_results: dict[str, Any] = {}

        try:
            # ---------------------------------------------------------
            # 1. INSPECT
            # ---------------------------------------------------------
            task = tasks[0]
            self.work_items.update_task(
                workflow_id,
                task["task_id"],
                "in_progress",
            )

            inspection = self.development_loop.worker.inspect()

            inspection_result = {
                "success": True,
                "stage": "inspect",
                "workspace": inspection,
            }

            self.work_items.update_task(
                workflow_id,
                task["task_id"],
                "completed",
                result=self._serialize_for_work_item(inspection_result),
            )
            completed_results["inspect"] = inspection_result

            # ---------------------------------------------------------
            # 2. PLAN
            # ---------------------------------------------------------
            task = tasks[1]
            self.work_items.update_task(
                workflow_id,
                task["task_id"],
                "in_progress",
            )

            planning = self.development_loop.inspect_and_plan(goal)

            if not planning.get("success", False):
                raise RuntimeError(
                    planning.get("message", "Development planning failed.")
                )

            plan = planning.get("plan", {})
            context["plan"] = plan

            planning_result = {
                "success": True,
                "stage": "plan",
                "plan": plan,
            }

            self.work_items.update_task(
                workflow_id,
                task["task_id"],
                "completed",
                result=self._serialize_for_work_item(planning_result),
            )
            completed_results["plan"] = planning_result

            # ---------------------------------------------------------
            # 3..7. BOUNDED DEVELOPMENT ITERATIONS
            # ---------------------------------------------------------
            max_iterations = self.development_loop.worker.MAX_ITERATIONS
            validation_result: dict[str, Any] | None = None
            successful_iteration: int | None = None

            for iteration in range(1, max_iterations + 1):
                context["iteration"] = iteration
                context["previous_validation"] = validation_result

                # Implementation task is entered only once.
                implementation_task = tasks[2]

                if iteration == 1:
                    self.work_items.update_task(
                        workflow_id,
                        implementation_task["task_id"],
                        "in_progress",
                    )

                development = self.development_loop.worker.generate_and_apply(
                    goal=goal,
                    iteration=iteration,
                    context=context,
                )

                if not development.get("success", False):
                    self._persist_workflow_failure(
                        workflow_id,
                        development,
                    )

                    return {
                        "success": False,
                        "state": "failed",
                        "workflow_id": workflow_id,
                        "stage": "implement",
                        "iteration": iteration,
                        "result": development,
                    }

                if (
                    iteration == 1
                    and self._goal_requires_changes(goal)
                    and not development.get("files_changed")
                    and not self._has_prior_applied_goal_changes(
                        goal,
                        workflow_id,
                    )
                ):
                    no_change_failure = {
                        "success": False,
                        "stage": "implement",
                        "code": "no_changes_generated",
                        "message": (
                            "The requested change goal produced no applied changes, "
                            "and no prior durable result proves this exact goal was "
                            "already implemented."
                        ),
                    }
                    self._persist_workflow_failure(
                        workflow_id,
                        no_change_failure,
                    )
                    return {
                        "success": False,
                        "state": "failed",
                        "workflow_id": workflow_id,
                        "stage": "implement",
                        "iteration": iteration,
                        "result": no_change_failure,
                    }

                if iteration == 1:
                    self.work_items.update_task(
                        workflow_id,
                        implementation_task["task_id"],
                        "completed",
                        result=self._serialize_for_work_item(development),
                    )

                # ---------------------------------------------
                # Validation
                # ---------------------------------------------
                validation_task = tasks[3]

                if iteration == 1:
                    self.work_items.update_task(
                        workflow_id,
                        validation_task["task_id"],
                        "in_progress",
                    )

                self.development_loop.worker.run_validation(
                    iteration,
                    ("python", "-m", "pytest", "-q"),
                )
                validation_result = self.development_loop.worker.result(
                    iteration
                )

                context["previous_validation"] = validation_result

                validation_success = (
                    validation_result.get("status") == "completed"
                    and validation_result.get("return_code") == 0
                )

                if validation_success:
                    if iteration == 1:
                        self.work_items.update_task(
                            workflow_id,
                            validation_task["task_id"],
                            "completed",
                            result=self._serialize_for_work_item(
                                validation_result
                            ),
                        )

                        for skipped_task in tasks[4:6]:
                            self.work_items.update_task(
                                workflow_id,
                                skipped_task["task_id"],
                                "in_progress",
                            )
                            self.work_items.update_task(
                                workflow_id,
                                skipped_task["task_id"],
                                "completed",
                                result=self._serialize_for_work_item(
                                    {
                                        "success": True,
                                        "stage": skipped_task["title"],
                                        "skipped": True,
                                        "reason": (
                                            "The initial implementation passed validation."
                                        ),
                                    }
                                ),
                            )

                    successful_iteration = iteration
                    break

                # Validation failed. Complete validation task so the
                # durable workflow can move to diagnosis.
                if iteration == 1:
                    self.work_items.update_task(
                        workflow_id,
                        validation_task["task_id"],
                        "completed",
                        result=self._serialize_for_work_item(
                            validation_result
                        ),
                    )

                # ---------------------------------------------
                # Diagnosis
                # ---------------------------------------------
                diagnosis_task = tasks[4]

                if iteration == 1:
                    self.work_items.update_task(
                        workflow_id,
                        diagnosis_task["task_id"],
                        "in_progress",
                    )

                diagnosis = {
                    "success": True,
                    "stage": "diagnose",
                    "iteration": iteration,
                    "validation": validation_result,
                }

                if iteration == 1:
                    self.work_items.update_task(
                        workflow_id,
                        diagnosis_task["task_id"],
                        "completed",
                        result=self._serialize_for_work_item(diagnosis),
                    )

                # ---------------------------------------------
                # Fix
                # ---------------------------------------------
                fix_task = tasks[5]

                if iteration == 1:
                    self.work_items.update_task(
                        workflow_id,
                        fix_task["task_id"],
                        "in_progress",
                    )

                context["diagnosis"] = diagnosis

                # The next loop iteration performs the bounded fix by
                # generating a new change set from the failure context.
                fix_result = {
                    "success": True,
                    "stage": "fix",
                    "iteration": iteration,
                    "message": "Failure context supplied to the next bounded development iteration.",
                }

                if iteration == 1:
                    self.work_items.update_task(
                        workflow_id,
                        fix_task["task_id"],
                        "completed",
                        result=self._serialize_for_work_item(fix_result),
                    )

                if not self.development_loop.worker.can_continue(iteration):
                    break

            if successful_iteration is None:
                failed_result = {
                    "success": False,
                    "stage": "validation",
                    "code": "max_iterations_reached",
                    "iterations": max_iterations,
                    "last_validation": validation_result,
                }
                self._persist_workflow_failure(
                    workflow_id,
                    failed_result,
                )

                return {
                    "success": False,
                    "state": "failed",
                    "workflow_id": workflow_id,
                    "stage": "validation",
                    "result": failed_result,
                }

            # ---------------------------------------------------------
            # 6/7. RE-RUN VALIDATION / VERIFY
            # ---------------------------------------------------------
            rerun_task = tasks[6]
            self.work_items.update_task(
                workflow_id,
                rerun_task["task_id"],
                "in_progress",
            )

            rerun_result = validation_result or {}

            self.work_items.update_task(
                workflow_id,
                rerun_task["task_id"],
                "completed",
                result=self._serialize_for_work_item(rerun_result),
            )

            # ---------------------------------------------------------
            # 8. VERIFY
            # ---------------------------------------------------------
            verify_task = tasks[7]
            self.work_items.update_task(
                workflow_id,
                verify_task["task_id"],
                "in_progress",
            )

            changed_files = sorted(
                {
                    path
                    for iteration in self.development_loop.worker.iterations
                    for path in iteration.files_changed
                }
            )
            missing_files = [
                path
                for path in changed_files
                if not self.development_loop.worker.boundary.exists(path)
            ]

            if missing_files:
                raise RuntimeError(
                    "Applied development files are missing: "
                    + ", ".join(missing_files)
                )

            verification = {
                "success": True,
                "stage": "verify",
                "goal": goal,
                "iteration": successful_iteration,
                "validation": validation_result,
                "changed_files": changed_files,
                "changed_files_exist": True,
                "workspace_boundary_enforced": True,
                "prior_goal_changes_reused": (
                    not changed_files
                    and self._has_prior_applied_goal_changes(
                        goal,
                        workflow_id,
                    )
                ),
            }

            self.work_items.update_task(
                workflow_id,
                verify_task["task_id"],
                "completed",
                result=self._serialize_for_work_item(verification),
            )

            # ---------------------------------------------------------
            # 9. RECORD
            # ---------------------------------------------------------
            record_task = tasks[8]
            self.work_items.update_task(
                workflow_id,
                record_task["task_id"],
                "in_progress",
            )

            final_result = {
                "success": True,
                "state": "completed",
                "workflow_id": workflow_id,
                "goal": goal,
                "iteration": successful_iteration,
                "validation": validation_result,
                "verification": verification,
            }

            self.work_items.update_task(
                workflow_id,
                record_task["task_id"],
                "completed",
                result=self._serialize_for_work_item(final_result),
            )

            completed = self.work_items.get_workflow(workflow_id)

            if (
                completed is None
                or completed.get("status") != "completed"
                or any(
                    item.get("status") != "completed"
                    for item in completed.get("tasks", [])
                )
            ):
                raise RuntimeError(
                    "Durable development workflow did not reach a fully completed state."
                )

            verification["durable_workflow_completed"] = True
            self.work_items.update_task(
                workflow_id,
                verify_task["task_id"],
                "completed",
                result=self._serialize_for_work_item(verification),
            )
            completed = self.work_items.get_workflow(workflow_id)

            return {
                **final_result,
                "workflow": completed,
            }

        except Exception as exc:
            failure = {
                "success": False,
                "stage": "execute",
                "code": "autonomous_development_error",
                "message": str(exc),
            }
            self._persist_workflow_failure(
                workflow_id,
                failure,
            )
            return {
                "success": False,
                "state": "failed",
                "workflow_id": workflow_id,
                "code": "autonomous_development_error",
                "message": str(exc),
            }

    def _persist_workflow_failure(
        self,
        workflow_id: str,
        failure: dict[str, Any],
    ) -> None:
        workflow = self.work_items.get_workflow(workflow_id)

        if workflow is None:
            return

        task = next(
            (
                item
                for item in workflow["tasks"]
                if item["status"] == "in_progress"
            ),
            None,
        ) or next(
            (
                item
                for item in workflow["tasks"]
                if item["status"] == "pending"
            ),
            None,
        )

        if task is not None:
            message = str(
                failure.get("message")
                or failure.get("code")
                or "Autonomous development failed."
            )[:1000]
            self.work_items.update_task(
                workflow_id,
                task["task_id"],
                "failed",
                blocker=message,
                result=self._serialize_for_work_item(failure),
            )

        workflow = self.work_items.get_workflow(workflow_id)

        if workflow is None:
            return

        for item in workflow["tasks"]:
            if item["status"] == "pending":
                self.work_items.update_task(
                    workflow_id,
                    item["task_id"],
                    "blocked",
                    blocker="Blocked because an earlier development stage failed.",
                )

    def _recover_stale_workflows(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        current_time = now or datetime.now(UTC)
        cutoff = current_time - timedelta(
            seconds=self.STALE_WORKFLOW_AFTER_SECONDS
        )
        recovered = 0

        for workflow in self.work_items.list_workflows(
            category="operations",
            limit=200,
        ):
            if workflow.get("status") != "in_progress":
                continue

            try:
                updated_at = datetime.fromisoformat(
                    workflow["updated_at"]
                )
            except (KeyError, TypeError, ValueError):
                continue

            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)

            if updated_at >= cutoff:
                continue

            active_tasks = [
                task
                for task in workflow.get("tasks", [])
                if task.get("status") == "in_progress"
            ]

            for task in active_tasks:
                self.work_items.update_task(
                    workflow["workflow_id"],
                    task["task_id"],
                    "failed",
                    blocker="Autonomous development was interrupted and exceeded the recovery window.",
                    result=self._serialize_for_work_item(
                        {
                            "success": False,
                            "code": "interrupted_workflow_recovered",
                            "message": "The active stage was not resumed because its outcome may be uncertain.",
                        }
                    ),
                )

            if not active_tasks:
                pending_task = next(
                    (
                        task
                        for task in workflow.get("tasks", [])
                        if task.get("status") == "pending"
                    ),
                    None,
                )
                if pending_task is not None:
                    self.work_items.update_task(
                        workflow["workflow_id"],
                        pending_task["task_id"],
                        "failed",
                        blocker="Autonomous development was interrupted before this stage started.",
                        result=self._serialize_for_work_item(
                            {
                                "success": False,
                                "code": "interrupted_workflow_recovered",
                            }
                        ),
                    )

            updated_workflow = self.work_items.get_workflow(
                workflow["workflow_id"]
            )
            if updated_workflow is None:
                continue

            for task in updated_workflow["tasks"]:
                if task.get("status") == "pending":
                    self.work_items.update_task(
                        workflow["workflow_id"],
                        task["task_id"],
                        "blocked",
                        blocker="Blocked because an earlier stage was interrupted.",
                    )

            recovered += 1

        return recovered

    @staticmethod
    def _goal_requires_changes(goal: str) -> bool:
        intent_words = {
            "add",
            "create",
            "implement",
            "write",
            "fix",
            "update",
            "modify",
            "complete",
        }
        words = {
            token.strip(".,:;()[]{}<>/\\").casefold()
            for token in goal.split()
        }
        return bool(intent_words.intersection(words))

    def _has_prior_applied_goal_changes(
        self,
        goal: str,
        current_workflow_id: str,
    ) -> bool:
        normalized_goal = " ".join(goal.split()).casefold()

        for workflow in self.work_items.list_workflows(
            category="operations",
            limit=200,
        ):
            if (
                workflow.get("workflow_id") == current_workflow_id
                or " ".join(workflow.get("request", "").split()).casefold()
                != normalized_goal
            ):
                continue

            implementation = next(
                (
                    task
                    for task in workflow.get("tasks", [])
                    if task.get("title", "").startswith("Implement ")
                ),
                None,
            )
            if implementation is None or not implementation.get("result"):
                continue

            try:
                result = json.loads(implementation["result"])
            except (TypeError, json.JSONDecodeError):
                continue

            applied_files = result.get("files_changed")
            if (
                isinstance(applied_files, list)
                and applied_files
                and all(
                    isinstance(path, str)
                    and self.development_loop.worker.boundary.exists(path)
                    for path in applied_files
                )
            ):
                return True

        return False

    def execute_existing_workflow(
        self,
        workflow_id: str,
        *,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        workflow = self.work_items.get_workflow(
            workflow_id
        )

        if workflow is None:
            return {
                "success": False,
                "state": "rejected",
                "code": "workflow_not_found",
                "workflow_id": workflow_id,
            }

        if workflow["category"] != "operations":
            return {
                "success": False,
                "state": "rejected",
                "code": "unsupported_workflow_category",
                "workflow_id": workflow_id,
            }

        if (
            session_id is not None
            and workflow.get("session_id")
            not in {
                None,
                session_id,
            }
        ):
            return {
                "success": False,
                "state": "rejected",
                "code": "session_mismatch",
                "workflow_id": workflow_id,
            }

        for task in workflow["tasks"]:
            if task["status"] == "completed":
                continue

            self.work_items.update_task(
                workflow_id,
                task["task_id"],
                "in_progress",
            )

            result = self._execute_task(
                task["title"]
            )

            if not result.get(
                "success",
                False,
            ):
                self.work_items.update_task(
                    workflow_id,
                    task["task_id"],
                    "failed",
                    blocker=result.get(
                        "message",
                        "Development task failed.",
                    ),
                    result=self._serialize_for_work_item(
                        result
                    ),
                )

                return {
                    "success": False,
                    "state": "failed",
                    "workflow_id": workflow_id,
                    "failed_task": task["title"],
                    "result": result,
                }

            self.work_items.update_task(
                workflow_id,
                task["task_id"],
                "completed",
                result=self._serialize_for_work_item(
                    result
                ),
            )

        completed = self.work_items.get_workflow(
            workflow_id
        )

        return {
            "success": True,
            "state": "completed",
            "workflow_id": workflow_id,
            "workflow": completed,
        }

    def inspect(
        self,
        run_id: str,
    ) -> dict[str, Any] | None:
        return self.recovery.get_run(
            run_id
        )

    def resume(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        return self.workflow_engine.resume(
            run_id
        )

    def cancel(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        cancelled = self.workflow_engine.cancel(
            run_id
        )

        return {
            "success": cancelled,
            "run_id": run_id,
            "state": (
                "cancelled"
                if cancelled
                else "not_running"
            ),
        }

    def list_workflows(
        self,
        *,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.work_items.list_workflows(
            category="operations",
            session_id=session_id,
            limit=limit,
        )

    def _execute_task(
        self,
        task: str,
    ) -> dict[str, Any]:
        """
        Execute one bounded autonomous-development task.

        Development tasks are handled by the dedicated
        development loop instead of being reinterpreted by
        the general WorkflowEngine planner.
        """

        task_lower = task.lower()

        # ---------------------------------
        # INSPECTION
        # ---------------------------------

        if "inspect" in task_lower:
            result = (
                self.development_loop.inspect_and_plan(
                    task
                )
            )

            return {
                "success": True,
                "stage": "inspect",
                "workspace": result.get(
                    "workspace"
                ),
                "plan": result.get(
                    "plan"
                ),
            }

        # ---------------------------------
        # PLANNING
        # ---------------------------------

        if "plan" in task_lower:
            result = (
                self.development_loop.inspect_and_plan(
                    task
                )
            )

            return {
                "success": True,
                "stage": "plan",
                "workspace": result.get(
                    "workspace"
                ),
                "plan": result.get(
                    "plan"
                ),
            }

        # ---------------------------------
        # IMPLEMENTATION
        # ---------------------------------

        if "implement" in task_lower:
            return {
                "success": False,
                "stage": "implement",
                "code": "development_provider_required",
                "message": (
                    "Implementation requires a configured "
                    "development code-generation provider."
                ),
            }

        # ---------------------------------
        # VALIDATION
        # ---------------------------------

        if (
            "validation" in task_lower
            or "re-run" in task_lower
        ):
            return {
                "success": False,
                "stage": "validation",
                "code": "implementation_required",
                "message": (
                    "Validation cannot proceed until "
                    "development changes have been "
                    "generated and applied."
                ),
            }

        # ---------------------------------
        # DIAGNOSIS
        # ---------------------------------

        if "diagnose" in task_lower:
            return {
                "success": True,
                "stage": "diagnose",
                "message": (
                    "Diagnosis stage is ready and requires "
                    "a validation result from the "
                    "implementation stage."
                ),
            }

        # ---------------------------------
        # FIX
        # ---------------------------------

        if "fix" in task_lower:
            return {
                "success": False,
                "stage": "fix",
                "code": "development_provider_required",
                "message": (
                    "Fix generation requires a configured "
                    "development code-generation provider."
                ),
            }

        # ---------------------------------
        # VERIFICATION
        # ---------------------------------

        if "verify" in task_lower:
            return {
                "success": True,
                "stage": "verify",
                "message": (
                    "Verification stage is available after "
                    "successful implementation and validation."
                ),
            }

        # ---------------------------------
        # RECORD
        # ---------------------------------

        if "record" in task_lower:
            return {
                "success": True,
                "stage": "record",
                "message": (
                    "Development result recording is complete."
                ),
            }

        # ---------------------------------
        # UNKNOWN TASK
        # ---------------------------------

        return {
            "success": False,
            "code": "unsupported_development_task",
            "message": (
                f"Unsupported development task: {task}"
            ),
        }

    def _serialize_for_work_item(
        self,
        result: Any,
    ) -> str:
        """
        Convert a task result into a bounded string suitable
        for WorkItemService persistence.

        WorkItemService has a 4000-character result limit.
        The full result remains available to the caller before
        persistence; only the durable work-item copy is bounded.
        """

        try:
            serialized = json.dumps(
                result,
                indent=2,
                default=str,
            )
        except (TypeError, ValueError):
            serialized = str(result)

        if len(serialized) <= self.MAX_STORED_RESULT_LENGTH:
            return serialized

        suffix = (
            "\n...[result truncated for work-item storage]"
        )

        available = (
            self.MAX_STORED_RESULT_LENGTH
            - len(suffix)
        )

        return (
            serialized[:available]
            + suffix
        )

    def _validate_goal(
        self,
        goal: str,
    ) -> str:
        if not isinstance(
            goal,
            str,
        ):
            raise ValueError(
                "Development goal must be a string."
            )

        goal = goal.strip()

        if not goal:
            raise ValueError(
                "Development goal cannot be empty."
            )

        if len(goal) > self.MAX_GOAL_LENGTH:
            raise ValueError(
                "Development goal cannot exceed "
                f"{self.MAX_GOAL_LENGTH} characters."
            )

        return goal