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
from app.services.autonomous_development.development_audit_service import DevelopmentAuditService
from app.services.autonomous_development.development_backlog_service import DevelopmentBacklogService
from app.services.autonomous_development.development_progress_service import DevelopmentProgressService
from app.services.autonomous_development.development_task_planner import DevelopmentTaskPlanner


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
    MAX_TASKS_PER_CONTINUATION = 3

    def __init__(
        self,
        workspace: str | Path = ".",
        workflow_engine: WorkflowEngine | None = None,
        work_items: WorkItemService | None = None,
        recovery: RunRecoveryService | None = None,
        backlog: DevelopmentBacklogService | None = None,
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

        self.backlog = backlog or DevelopmentBacklogService(
            self.workspace / "memory" / "development_backlog.json"
        )
        self.audit_service = DevelopmentAuditService(
            self.development_loop.worker,
            work_items=self.work_items,
            recovery=self.recovery,
        )
        self.task_planner = DevelopmentTaskPlanner(self.backlog)
        self.progress = DevelopmentProgressService(self.backlog)

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
        _workflow_id: str | None = None,
        _recovery_run_id: str | None = None,
        _backlog_program_id: str | None = None,
        _backlog_task: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a bounded autonomous development workflow.

        The workflow is durable at the WorkItemService level while the
        development loop performs bounded inspect -> plan -> generate ->
        apply -> validate -> fix/retest -> verify execution.
        """
        goal = self._validate_goal(goal)
        self._recover_stale_workflows()

        if self._is_continuation_request(goal):
            return self._continue_development_program(
                goal,
                session_id=session_id,
            )

        if self._is_broad_completion_goal(goal):
            return self._execute_broad_goal(
                goal,
                session_id=session_id,
            )

        if _workflow_id is not None and _recovery_run_id is not None:
            existing_workflow = self.work_items.get_workflow(_workflow_id)
            if existing_workflow is None:
                return {
                    "success": False,
                    "state": "rejected",
                    "code": "work_item_workflow_missing",
                    "workflow_id": _workflow_id,
                    "recovery_run_id": _recovery_run_id,
                }
            workflow = {
                "workflow_id": _workflow_id,
                "tasks": existing_workflow["tasks"],
            }
            recovery_run_id = _recovery_run_id
            previous_run = self.recovery.get_run(recovery_run_id)
            completed_stages = {
                item["stage"]
                for item in (previous_run or {}).get("stage_records", [])
                if item.get("status") == "completed"
            }
        else:
            workflow = self.create_development_workflow(
                goal,
                session_id=session_id,
            )
            recovery_plan = {
                "success": True,
                "autonomous_development": True,
                "workflow_id": workflow["workflow_id"],
                "steps": [
                    "inspect",
                    "plan",
                    "generate_changes",
                    "apply_changes",
                    "validate",
                    "diagnose",
                    "fix",
                    "verify",
                    "record",
                ],
            }
            if _backlog_program_id is not None and _backlog_task is not None:
                recovery_plan["development_program_id"] = _backlog_program_id
                recovery_plan["development_task_id"] = _backlog_task["task_id"]
            recovery_run = self.recovery.create_run(
                goal,
                recovery_plan,
                session_id,
            )
            recovery_run_id = recovery_run["run_id"]
            completed_stages = set()
            if _backlog_program_id is not None and _backlog_task is not None:
                self.backlog.link_recovery_run(
                    _backlog_program_id,
                    _backlog_task["task_id"],
                    recovery_run_id,
                )
                self.progress.checkpoint(
                    _backlog_program_id,
                    _backlog_task["task_id"],
                    iteration=max(1, _backlog_task.get("iteration", 0)),
                    recovery_run_id=recovery_run_id,
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
            if "inspect" in completed_stages:
                inspection = self.development_loop.worker.inspect()
            else:
                task = tasks[0]
                self.recovery.update(
                    recovery_run_id,
                    "start_stage",
                    stage="inspect",
                )
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
                self.recovery.update(
                    recovery_run_id,
                    "complete_stage",
                    stage="inspect",
                    result={"file_count": inspection.get("file_count")},
                )
                completed_results["inspect"] = inspection_result

            # ---------------------------------------------------------
            # 2. PLAN
            # ---------------------------------------------------------
            if "plan" in completed_stages:
                plan_record = next(
                    item
                    for item in self.recovery.get_run(recovery_run_id)["stage_records"]
                    if item["stage"] == "plan" and item["status"] == "completed"
                )
                plan = plan_record.get("result", {})
            else:
                task = tasks[1]
                self.recovery.update(
                    recovery_run_id,
                    "start_stage",
                    stage="plan",
                )
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
                self.recovery.update(
                    recovery_run_id,
                    "complete_stage",
                    stage="plan",
                    result=plan,
                )
                completed_results["plan"] = planning_result

            context["plan"] = plan
            if _backlog_task is not None:
                plan = {
                    **plan,
                    "acceptance_criteria": _backlog_task.get("acceptance_criteria", []),
                    "relevant_files": _backlog_task.get("relevant_files", []),
                }
                context["plan"] = plan
                context["task"] = _backlog_task.get("objective", goal)
                context["acceptance_criteria"] = _backlog_task.get("acceptance_criteria", [])
                context["relevant_files"] = _backlog_task.get("relevant_files", [])
                context["previous_validation"] = _backlog_task.get("last_validation")
                context["previous_error"] = _backlog_task.get("last_error")

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
                    self.recovery.update(
                        recovery_run_id,
                        "start_stage",
                        stage="generate_changes",
                    )
                    self.work_items.update_task(
                        workflow_id,
                        implementation_task["task_id"],
                        "in_progress",
                    )

                prior_goal_files = (
                    self._prior_applied_goal_files(goal, workflow_id)
                    if iteration == 1
                    else []
                )
                if prior_goal_files:
                    self.development_loop.worker.begin_iteration(iteration)
                    generated = {
                        "success": True,
                        "status": "no_change",
                        "already_satisfied": True,
                        "evidence": (
                            "A prior exact-goal workflow recorded these applied files, "
                            "and each still exists inside the authorized workspace."
                        ),
                        "changes": [],
                    }
                else:
                    generated = self.development_loop.worker.generate_changes(
                        goal=goal,
                        iteration=iteration,
                        context={
                            **context,
                            "task": goal,
                            "acceptance_criteria": plan.get(
                                "acceptance_criteria",
                                [goal],
                            ),
                            "relevant_files": plan.get("relevant_files", []),
                        },
                    )

                if not generated.get("success", False):
                    self.recovery.update(
                        recovery_run_id,
                        "fail_stage",
                        stage="generate_changes",
                        error=generated.get("message") or generated.get("code"),
                    )
                    self._persist_workflow_failure(
                        workflow_id,
                        generated,
                    )

                    return {
                        "success": False,
                        "state": "failed",
                        "workflow_id": workflow_id,
                        "recovery_run_id": recovery_run_id,
                        "stage": "implement",
                        "iteration": iteration,
                        "result": generated,
                    }

                generated_changes = generated.get("changes")
                if not isinstance(generated_changes, list):
                    generated_failure = {
                        "success": False,
                        "code": "invalid_provider_changes",
                        "message": "Provider did not return a changes list.",
                    }
                    self.recovery.update(
                        recovery_run_id,
                        "fail_stage",
                        stage="generate_changes",
                        error=generated_failure["message"],
                    )
                    self._persist_workflow_failure(workflow_id, generated_failure)
                    return {
                        "success": False,
                        "state": "failed",
                        "workflow_id": workflow_id,
                        "recovery_run_id": recovery_run_id,
                        "stage": "implement",
                        "iteration": iteration,
                        "result": generated_failure,
                    }

                no_change_response = (
                    generated.get("status") == "no_change"
                    or not generated_changes
                )
                prior_files: list[str] = []
                if no_change_response:
                    prior_files = self._prior_applied_goal_files(
                        goal,
                        workflow_id,
                    )
                    if not prior_files:
                        no_change_failure = {
                            "success": False,
                            "stage": "implement",
                            "code": "no_changes_generated",
                            "message": (
                                "Provider reported no changes and no durable matching "
                                "artifact exists to prove the requested goal is complete."
                            ),
                        }
                        self.recovery.update(
                            recovery_run_id,
                            "fail_stage",
                            stage="generate_changes",
                            error=no_change_failure["message"],
                        )
                        self._persist_workflow_failure(workflow_id, no_change_failure)
                        return {
                            "success": False,
                            "state": "failed",
                            "workflow_id": workflow_id,
                            "recovery_run_id": recovery_run_id,
                            "stage": "implement",
                            "iteration": iteration,
                            "result": no_change_failure,
                        }

                if iteration == 1:
                    self.recovery.update(
                        recovery_run_id,
                        "complete_stage",
                        stage="generate_changes",
                        result={
                            "iteration": iteration,
                            "change_count": len(generated_changes),
                            "no_change": no_change_response,
                        },
                    )
                    self.recovery.update(
                        recovery_run_id,
                        "start_stage",
                        stage="apply_changes",
                    )

                if no_change_response:
                    development = {
                        "success": True,
                        "files_changed": prior_files,
                        "no_change_reused": True,
                        "evidence": generated.get("evidence"),
                    }
                else:
                    development = self.development_loop.worker.apply_changes(
                        iteration=iteration,
                        changes=generated_changes,
                    )

                if not development.get("success", False):
                    self.recovery.update(
                        recovery_run_id,
                        "fail_stage",
                        stage="apply_changes",
                        error=development.get("message") or development.get("code"),
                    )
                    self._persist_workflow_failure(workflow_id, development)
                    return {
                        "success": False,
                        "state": "failed",
                        "workflow_id": workflow_id,
                        "recovery_run_id": recovery_run_id,
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
                    self.recovery.update(
                        recovery_run_id,
                        "fail_stage",
                        stage="apply_changes",
                        error=no_change_failure["message"],
                    )
                    return {
                        "success": False,
                        "state": "failed",
                        "workflow_id": workflow_id,
                        "recovery_run_id": recovery_run_id,
                        "stage": "implement",
                        "iteration": iteration,
                        "result": no_change_failure,
                    }

                if iteration == 1:
                    self.recovery.update(
                        recovery_run_id,
                        "complete_stage",
                        stage="apply_changes",
                        result={
                            "iteration": iteration,
                            "files_changed": development.get("files_changed", []),
                        },
                    )
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
                    self.recovery.update(
                        recovery_run_id,
                        "start_stage",
                        stage="validate",
                    )
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
                        self.recovery.update(
                            recovery_run_id,
                            "complete_stage",
                            stage="validate",
                            result=validation_result,
                        )
                        self.work_items.update_task(
                            workflow_id,
                            validation_task["task_id"],
                            "completed",
                            result=self._serialize_for_work_item(
                                validation_result
                            ),
                        )

                        for skipped_task in tasks[4:6]:
                            recovery_stage = (
                                "diagnose"
                                if skipped_task is tasks[4]
                                else "fix"
                            )
                            self.recovery.update(
                                recovery_run_id,
                                "start_stage",
                                stage=recovery_stage,
                            )
                            self.recovery.update(
                                recovery_run_id,
                                "complete_stage",
                                stage=recovery_stage,
                                result={
                                    "skipped": True,
                                    "reason": "Initial validation passed.",
                                },
                            )
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
                    self.recovery.update(
                        recovery_run_id,
                        "complete_stage",
                        stage="validate",
                        result=validation_result,
                    )
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
                    self.recovery.update(
                        recovery_run_id,
                        "start_stage",
                        stage="diagnose",
                    )
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
                    self.recovery.update(
                        recovery_run_id,
                        "complete_stage",
                        stage="diagnose",
                        result=diagnosis,
                    )
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
                    self.recovery.update(
                        recovery_run_id,
                        "start_stage",
                        stage="fix",
                    )
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
                    self.recovery.update(
                        recovery_run_id,
                        "complete_stage",
                        stage="fix",
                        result=fix_result,
                    )
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
                current_stage = self.recovery.get_run(recovery_run_id).get("current_stage")
                if current_stage and current_stage in {"validate", "diagnose", "fix"}:
                    self.recovery.update(
                        recovery_run_id,
                        "fail_stage",
                        stage=current_stage,
                        error=failed_result["message"] if "message" in failed_result else failed_result["code"],
                    )

                return {
                    "success": False,
                    "state": "failed",
                    "workflow_id": workflow_id,
                    "recovery_run_id": recovery_run_id,
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
            self.recovery.update(
                recovery_run_id,
                "start_stage",
                stage="verify",
            )
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
            self.recovery.update(
                recovery_run_id,
                "complete_stage",
                stage="verify",
                result=verification,
            )

            # ---------------------------------------------------------
            # 9. RECORD
            # ---------------------------------------------------------
            record_task = tasks[8]
            self.recovery.update(
                recovery_run_id,
                "start_stage",
                stage="record",
            )
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
            self.recovery.update(
                recovery_run_id,
                "complete_stage",
                stage="record",
                result={"workflow_id": workflow_id},
            )
            self.recovery.update(
                recovery_run_id,
                "complete_run",
                last_completed_stage="record",
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
                "recovery_run_id": recovery_run_id,
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
            recovery_state = self.recovery.get_run(recovery_run_id)
            current_stage = recovery_state.get("current_stage") if recovery_state else None
            if current_stage:
                try:
                    self.recovery.update(
                        recovery_run_id,
                        "fail_stage",
                        stage=current_stage,
                        error=str(exc),
                    )
                except Exception:
                    pass
            return {
                "success": False,
                "state": "failed",
                "workflow_id": workflow_id,
                "recovery_run_id": recovery_run_id,
                "code": "autonomous_development_error",
                "message": str(exc),
            }

    def _continue_development_program(
        self,
        request: str,
        *,
        session_id: str | None,
    ) -> dict[str, Any]:
        audit = self.audit_service.run()
        program = self.task_planner.create_or_resume_program(
            request,
            audit,
        )
        for task in program["tasks"]:
            error = task.get("last_error")
            if task.get("status") not in {"blocked", "failed"} or not isinstance(error, dict):
                continue
            diagnosis = self.progress.diagnose_failure(error, task.get("last_validation"))
            message = error.get("message")
            if error.get("code") == "resume_limit_reached":
                message = "Recovery run reached the configured maximum resume count."
            corrected = {
                **error,
                "message": message or "Development task remains blocked.",
                **diagnosis,
            }
            if corrected != error:
                self.backlog.update_task(
                    program["program_id"],
                    task["task_id"],
                    last_error=corrected,
                )
        program = self.backlog.get_program(program["program_id"])

        if not program["tasks"]:
            self.backlog.set_program_status(
                program["program_id"],
                "blocked",
                completion_blockers=audit.get("completion_blockers", [
                    "No evidence-backed task is available in this bounded audit."
                ]),
            )
            return {
                "success": False,
                "state": "blocked",
                "code": "no_verified_work_items",
                "program_id": program["program_id"],
                "audit": audit or program.get("audit"),
                "message": (
                    "The bounded audit has no evidence-backed tasks. The program remains "
                    "durable and blocked rather than claiming Lumira is complete."
                ),
            }

        self.backlog.set_program_status(program["program_id"], "in_progress")
        results: list[dict[str, Any]] = []
        attempted: set[str] = set()
        completed_count = 0

        while len(results) < self.MAX_TASKS_PER_CONTINUATION:
            current = self.backlog.get_program(program["program_id"])
            interrupted = next(
                (
                    task for task in current["tasks"]
                    if task["status"] == "in_progress"
                    and task["task_id"] not in attempted
                ),
                None,
            )
            task = interrupted or self.backlog.next_ready_task(
                program["program_id"],
                exclude_task_ids=attempted,
            )
            if task is None:
                break

            attempted.add(task["task_id"])
            if task["status"] != "in_progress":
                task = self.progress.start(
                    program["program_id"],
                    task["task_id"],
                    iteration=max(1, task.get("iteration", 0)),
                )
                if task["status"] != "in_progress":
                    attempted.add(task["task_id"])
                    results.append({
                        "task_id": task["task_id"],
                        "objective": task["objective"],
                        "result": {
                            "success": False,
                            "state": "blocked",
                            "code": "attempt_limit_reached",
                            "message": "Bounded task attempts are exhausted.",
                        },
                    })
                    continue

            recovery_id = task.get("recovery_run_id") or task.get("resume_run_id")
            if recovery_id:
                recovery_state = self.recovery.get_run(recovery_id)
                if recovery_state and recovery_state.get("status") != "completed":
                    task_result = self.resume(recovery_id)
                elif recovery_state and recovery_state.get("status") == "completed":
                    task_result = {
                        "success": False,
                        "state": "rejected",
                        "code": "run_already_completed_without_backlog_checkpoint",
                        "recovery_run_id": recovery_id,
                    }
                else:
                    task_result = {
                        "success": False,
                        "state": "blocked",
                        "code": "recovery_run_missing",
                        "recovery_run_id": recovery_id,
                    }
            else:
                task_result = self.execute(
                    task["objective"],
                    session_id=session_id,
                    _backlog_program_id=program["program_id"],
                    _backlog_task=task,
                )

            results.append({
                "task_id": task["task_id"],
                "objective": task["objective"],
                "result": task_result,
            })

            validation = task_result.get("validation") or task_result.get("result", {}).get("validation") or {}
            if task_result.get("success") is True:
                if not validation:
                    recovery_id = task_result.get("recovery_run_id") or task.get("recovery_run_id")
                    recovery_state = self.recovery.get_run(recovery_id) if recovery_id else None
                    validation_record = next(
                        (stage for stage in (recovery_state or {}).get("stage_records", []) if stage.get("stage") == "validate" and stage.get("status") == "completed"),
                        {},
                    )
                    validation = validation_record.get("result", {})
                if validation.get("status") == "completed" and validation.get("return_code") == 0:
                    self.progress.complete(
                        program["program_id"],
                        task["task_id"],
                        result=task_result,
                        validation=validation,
                    )
                    completed_count += 1
                    continue

            error = task_result.get("result") if isinstance(task_result.get("result"), dict) else task_result
            code = error.get("code", "development_task_failed") if isinstance(error, dict) else "development_task_failed"
            message = error.get("message", "Development task did not satisfy its acceptance criteria.") if isinstance(error, dict) else str(error)
            retryable = code.startswith("provider_") or code in {
                "provider_retry_exhausted",
                "resumed_validation_failed",
                "max_iterations_reached",
            }
            self.progress.fail_or_block(
                program["program_id"],
                task["task_id"],
                error={
                    "code": code,
                    "message": message,
                    "recovery_run_id": task_result.get("recovery_run_id") or recovery_id,
                    "recommended_next_action": "Retry with corrected context or select an independent dependency-ready task.",
                },
                validation=validation or None,
                retryable=retryable,
            )

        final = self.backlog.get_program(program["program_id"])
        complete = bool(final["tasks"]) and all(task["status"] == "completed" for task in final["tasks"])
        if complete:
            final_audit = self.audit_service.run()
            if final_audit.get("findings"):
                previous_task_count = len(final["tasks"])
                refreshed = self.task_planner.create_or_resume_program(request, final_audit)
                added_task_count = max(0, len(refreshed["tasks"]) - previous_task_count)
                if added_task_count:
                    self.backlog.set_program_status(refreshed["program_id"], "in_progress")
                    return {
                        "success": False,
                        "state": "in_progress",
                        "code": "final_audit_found_more_work",
                        "program_id": refreshed["program_id"],
                        "completed_tasks": completed_count,
                        "added_task_count": added_task_count,
                        "audit": final_audit,
                        "message": "Final audit found additional evidence-backed work; rerun continuation to append the next bounded batch.",
                    }
            if final_audit.get("completion_ready") is not True:
                self.backlog.set_program_status(
                    program["program_id"],
                    "blocked",
                    completion_blockers=final_audit.get("completion_blockers", [
                        "Final whole-program audit is not available.",
                    ]),
                )
                return {
                    "success": False,
                    "state": "blocked",
                    "code": "final_audit_incomplete",
                    "program_id": program["program_id"],
                    "completed_tasks": completed_count,
                    "audit": final_audit,
                    "completion_blockers": final_audit.get("completion_blockers", []),
                    "message": "All current tasks passed, but the available bounded audit cannot verify whole-Lumira completion.",
                }
            self.backlog.set_program_status(program["program_id"], "completed", completion_blockers=[])

        final = self.backlog.get_program(program["program_id"])
        pending = [task for task in final["tasks"] if task["status"] in {"planned", "in_progress"}]
        blocked = [task for task in final["tasks"] if task["status"] in {"blocked", "failed"}]
        if pending:
            self.backlog.set_program_status(program["program_id"], "in_progress")
        elif blocked:
            self.backlog.set_program_status(
                program["program_id"],
                "blocked",
                completion_blockers=[
                    f"{task['objective']}: {(task.get('last_error') or {}).get('message', 'Task is blocked.')}"
                    for task in blocked[:20]
                ],
            )
        final = self.backlog.get_program(program["program_id"])
        return {
            "success": complete,
            "state": "completed" if complete else "blocked" if blocked and not pending else "in_progress",
            "program_id": final["program_id"],
            "completed_tasks_this_run": completed_count,
            "remaining_task_count": len(pending),
            "blocked_task_count": len(blocked),
            "results": results,
            "program": final,
        }

    @staticmethod
    def _is_continuation_request(goal: str) -> bool:
        normalized = " ".join(goal.casefold().strip().split())
        return normalized in {
            "continue",
            "continue lumira development",
            "continue development",
            "continue remaining development",
            "complete remaining lumira development",
            "complete all remaining lumira development",
            "complete all remaining development",
            "finish lumira development",
        }

    def _execute_broad_goal(
        self,
        goal: str,
        *,
        session_id: str | None,
    ) -> dict[str, Any]:
        inspection = self.development_loop.worker.inspect()
        plan = self.development_loop.planner.create_plan(
            goal,
            inspection,
        )
        planned_items = plan.get("work_items", [])
        if not isinstance(planned_items, list):
            planned_items = []
        planned_items = planned_items[: self.development_loop.planner.MAX_WORK_ITEMS]

        if not planned_items:
            workflow = self.work_items.create_workflow(
                category="operations",
                title="Bounded Lumira completion audit",
                request=goal,
                tasks=["No verified incomplete implementation item was found by the bounded audit."],
                session_id=session_id,
            )
            self.work_items.update_task(
                workflow["workflow_id"],
                workflow["tasks"][0]["task_id"],
                "blocked",
                blocker=(
                    "The bounded repository audit produced no evidence-backed task; "
                    "no repository-wide model changes were attempted."
                ),
                result=self._serialize_for_work_item(
                    {
                        "audit_file_count": inspection.get("file_count"),
                        "audit_findings": 0,
                        "success": False,
                    }
                ),
            )
            return {
                "success": False,
                "state": "blocked",
                "code": "no_verified_work_items",
                "workflow_id": workflow["workflow_id"],
                "audit_file_count": inspection.get("file_count"),
                "audit_findings": inspection.get("audit_findings", []),
            }

        task_titles = [
            str(item.get("objective", ""))[:500]
            for item in planned_items
            if isinstance(item, dict) and item.get("objective")
        ]
        if not task_titles:
            return {
                "success": False,
                "state": "blocked",
                "code": "invalid_decomposition",
                "message": "The bounded audit did not produce valid work-item objectives.",
            }

        parent = self.work_items.create_workflow(
            category="operations",
            title="Bounded Lumira completion workflow",
            request=goal,
            tasks=task_titles,
            session_id=session_id,
        )
        results = []

        for index, (item, task) in enumerate(zip(planned_items, parent["tasks"])):
            self.work_items.update_task(
                parent["workflow_id"],
                task["task_id"],
                "in_progress",
                result=self._serialize_for_work_item(
                    {
                        "objective": item["objective"],
                        "relevant_files": item.get("relevant_files", []),
                        "dependencies": item.get("dependencies", []),
                        "acceptance_criteria": item.get("acceptance_criteria", []),
                        "validation_command": item.get("validation_command"),
                        "bounded_scope": item.get("bounded_scope"),
                        "status": "in_progress",
                    }
                ),
            )
            child = self.execute(
                item["objective"],
                session_id=session_id,
            )
            results.append(
                {
                    "work_item": item,
                    "result": child,
                }
            )
            if not child.get("success"):
                self.work_items.update_task(
                    parent["workflow_id"],
                    task["task_id"],
                    "failed",
                    blocker=(
                        child.get("result", {}).get("message")
                        or child.get("message")
                        or child.get("code")
                        or "Bounded child development task failed."
                    )[:1000],
                    result=self._serialize_for_work_item(child),
                )
                latest = self.work_items.get_workflow(parent["workflow_id"])
                for pending in latest["tasks"][index + 1 :]:
                    if pending["status"] == "pending":
                        self.work_items.update_task(
                            parent["workflow_id"],
                            pending["task_id"],
                            "blocked",
                            blocker="Blocked because a prerequisite audit work item failed.",
                        )
                return {
                    "success": False,
                    "state": "failed",
                    "workflow_id": parent["workflow_id"],
                    "decomposed_work_item_count": len(planned_items),
                    "failed_work_item": item,
                    "results": results,
                    "workflow": self.work_items.get_workflow(parent["workflow_id"]),
                }

            child_workflow = child.get("workflow", {})
            task_result = {
                "objective": item["objective"],
                "acceptance_criteria": item.get("acceptance_criteria", []),
                "relevant_files": item.get("relevant_files", []),
                "child_workflow_id": child.get("workflow_id"),
                "child_state": child.get("state"),
                "validation": child.get("validation"),
                "verified": (
                    child.get("success") is True
                    and child_workflow.get("status") == "completed"
                ),
            }
            self.work_items.update_task(
                parent["workflow_id"],
                task["task_id"],
                "completed",
                result=self._serialize_for_work_item(task_result),
            )

        final_workflow = self.work_items.get_workflow(parent["workflow_id"])
        complete = bool(
            final_workflow
            and final_workflow.get("status") == "completed"
            and all(task.get("status") == "completed" for task in final_workflow["tasks"])
        )
        return {
            "success": complete,
            "state": "completed" if complete else "failed",
            "workflow_id": parent["workflow_id"],
            "audit_file_count": inspection.get("file_count"),
            "decomposed_work_item_count": len(planned_items),
            "results": results,
            "workflow": final_workflow,
        }

    @staticmethod
    def _is_broad_completion_goal(goal: str) -> bool:
        normalized = " ".join(goal.casefold().split())
        return any(
            phrase in normalized
            for phrase in (
                "complete all remaining lumira development",
                "complete all remaining development",
                "complete lumira development",
                "finish all remaining lumira development",
            )
        )
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

    def _prior_applied_goal_files(
        self,
        goal: str,
        current_workflow_id: str,
    ) -> list[str]:
        normalized_goal = " ".join(goal.split()).casefold()
        for workflow in self.work_items.list_workflows(category="operations", limit=200):
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
                    and task.get("status") in {"completed", "failed"}
                ),
                None,
            )
            if implementation is None or not implementation.get("result"):
                continue
            try:
                result = json.loads(implementation["result"])
            except (TypeError, json.JSONDecodeError):
                continue
            files = result.get("files_changed")
            if (
                isinstance(files, list)
                and files
                and all(
                    isinstance(path, str)
                    and self.development_loop.worker.boundary.exists(path)
                    for path in files
                )
            ):
                return files
        return []

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
        run = self.recovery.get_run(
            run_id
        )

        if run is None:
            return None

        plan = run.get("plan", {})
        workflow_id = plan.get("workflow_id") if plan.get("autonomous_development") else None
        program_id = plan.get("development_program_id") if isinstance(plan, dict) else None
        task_id = plan.get("development_task_id") if isinstance(plan, dict) else None
        program = self.backlog.get_program(program_id) if program_id else None
        task = next(
            (item for item in (program or {}).get("tasks", []) if item.get("task_id") == task_id),
            None,
        )
        current_stage_record = next(
            (item for item in run.get("stage_records", []) if item.get("stage") == run.get("current_stage")),
            {},
        )
        return {
            **run,
            "development_program_id": program_id,
            "development_task_id": task_id,
            "development_task": task,
            "current_iteration": (
                current_stage_record.get("result", {}).get("iteration")
                if isinstance(current_stage_record.get("result"), dict)
                else (task or {}).get("iteration")
            ),
            "last_validation": (task or {}).get("last_validation"),
            "work_item_workflow": (
                self.work_items.get_workflow(workflow_id)
                if workflow_id
                else None
            ),
        }

    def resume(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        run = self.recovery.get_run(run_id)
        if run is None:
            return {
                "success": False,
                "state": "rejected",
                "code": "run_not_found",
                "run_id": run_id,
            }

        plan = run.get("plan", {})
        if not isinstance(plan, dict) or not plan.get("autonomous_development"):
            return self.workflow_engine.resume(run_id)

        if run.get("status") == "completed":
            return {
                "success": False,
                "state": "rejected",
                "code": "run_already_completed",
                "run_id": run_id,
            }

        if run.get("resume_count", 0) >= self.recovery.MAX_RESUMES:
            return {
                "success": False,
                "state": "blocked",
                "code": "resume_limit_reached",
                "run_id": run_id,
            }

        session_id = run.get("session_id")
        if session_id:
            from app.services.sessions.session_manager_service import SessionManagerService

            session = SessionManagerService().get_session(session_id)
            if session is None or session.get("status") == "closed":
                return {
                    "success": False,
                    "state": "rejected",
                    "code": "session_closed" if session else "session_not_found",
                    "run_id": run_id,
                }

        if not run.get("resume_allowed"):
            self.recovery.update(
                run_id,
                "block",
                error="autonomous_side_effect_outcome_unknown",
            )
            return {
                "success": False,
                "state": "blocked",
                "code": "manual_reconciliation_required",
                "run_id": run_id,
                "recovery": self.recovery.get_run(run_id),
            }

        safe_stage = run.get("safe_resume_point")
        if safe_stage == "generate_changes":
            workflow_id = plan.get("workflow_id")
            workflow = self.work_items.get_workflow(workflow_id)
            if workflow is None:
                self.recovery.update(
                    run_id,
                    "block",
                    error="autonomous_work_item_missing",
                )
                return {
                    "success": False,
                    "state": "blocked",
                    "code": "work_item_workflow_missing",
                    "run_id": run_id,
                }
            try:
                self.recovery.update(run_id, "resume")
            except ValueError as exc:
                return {
                    "success": False,
                    "state": "blocked",
                    "code": "resume_limit_reached",
                    "run_id": run_id,
                    "message": str(exc),
                }
            result = self.execute(
                run["goal"],
                session_id=session_id,
                _workflow_id=workflow_id,
                _recovery_run_id=run_id,
            )
            return {
                **result,
                "resumed": True,
                "recovery_run_id": run_id,
            }

        if safe_stage != "validate":
            return {
                "success": False,
                "state": "blocked",
                "code": "unsupported_safe_resume_point",
                "run_id": run_id,
                "safe_resume_point": safe_stage,
            }

        workflow_id = plan.get("workflow_id")
        workflow = self.work_items.get_workflow(workflow_id)
        if workflow is None:
            self.recovery.update(
                run_id,
                "block",
                error="autonomous_work_item_missing",
            )
            return {
                "success": False,
                "state": "blocked",
                "code": "work_item_workflow_missing",
                "run_id": run_id,
            }

        applied = next(
            (
                item
                for item in run.get("stage_records", [])
                if item.get("stage") == "apply_changes"
                and item.get("status") == "completed"
            ),
            None,
        )
        applied_result = applied.get("result", {}) if applied else {}
        iteration_number = applied_result.get("iteration")
        changed_files = applied_result.get("files_changed", [])
        if not isinstance(iteration_number, int) or not isinstance(changed_files, list):
            self.recovery.update(
                run_id,
                "block",
                error="autonomous_apply_checkpoint_invalid",
            )
            return {
                "success": False,
                "state": "blocked",
                "code": "apply_checkpoint_invalid",
                "run_id": run_id,
            }

        try:
            self.recovery.update(run_id, "resume")
            self.recovery.update(run_id, "start_stage", stage="validate")
            worker = self.development_loop.worker
            worker.begin_iteration(iteration_number)
            worker.run_validation(
                iteration_number,
                ("python", "-m", "pytest", "-q"),
            )
            validation = worker.result(iteration_number)
            if validation.get("status") != "completed" or validation.get("return_code") != 0:
                self.recovery.update(
                    run_id,
                    "fail_stage",
                    stage="validate",
                    error="resumed_validation_failed",
                )
                self._persist_workflow_failure(
                    workflow_id,
                    {
                        "code": "resumed_validation_failed",
                        "message": validation.get("output", "Validation failed."),
                    },
                )
                return {
                    "success": False,
                    "state": "failed",
                    "code": "resumed_validation_failed",
                    "run_id": run_id,
                    "validation": validation,
                }

            self.recovery.update(
                run_id,
                "complete_stage",
                stage="validate",
                result=validation,
            )
            tasks = workflow["tasks"]
            validation_task = tasks[3]
            if validation_task["status"] == "pending":
                self.work_items.update_task(
                    workflow_id,
                    validation_task["task_id"],
                    "in_progress",
                )
            if validation_task["status"] != "completed":
                self.work_items.update_task(
                    workflow_id,
                    validation_task["task_id"],
                    "completed",
                    result=self._serialize_for_work_item(validation),
                )

            for task in tasks[4:6]:
                current = self.work_items.get_workflow(workflow_id)
                task_state = next(item for item in current["tasks"] if item["task_id"] == task["task_id"])
                if task_state["status"] == "pending":
                    self.work_items.update_task(workflow_id, task["task_id"], "in_progress")
                    self.work_items.update_task(
                        workflow_id,
                        task["task_id"],
                        "completed",
                        result=self._serialize_for_work_item(
                            {"skipped": True, "reason": "Recovery validation passed; no fix was needed."}
                        ),
                    )

            rerun_task = tasks[6]
            current = self.work_items.get_workflow(workflow_id)
            rerun_state = next(item for item in current["tasks"] if item["task_id"] == rerun_task["task_id"])
            if rerun_state["status"] == "pending":
                self.work_items.update_task(workflow_id, rerun_task["task_id"], "in_progress")
                self.work_items.update_task(
                    workflow_id,
                    rerun_task["task_id"],
                    "completed",
                    result=self._serialize_for_work_item(validation),
                )

            self.recovery.update(run_id, "start_stage", stage="verify")
            missing = [path for path in changed_files if not worker.boundary.exists(path)]
            if missing:
                raise RuntimeError("Applied files missing during recovery verification.")
            verification = {
                "success": True,
                "stage": "verify",
                "iteration": iteration_number,
                "validation": validation,
                "changed_files": changed_files,
                "changed_files_exist": True,
                "resumed": True,
            }
            verify_task = tasks[7]
            current = self.work_items.get_workflow(workflow_id)
            verify_state = next(item for item in current["tasks"] if item["task_id"] == verify_task["task_id"])
            if verify_state["status"] == "pending":
                self.work_items.update_task(workflow_id, verify_task["task_id"], "in_progress")
            if verify_state["status"] != "completed":
                self.work_items.update_task(
                    workflow_id,
                    verify_task["task_id"],
                    "completed",
                    result=self._serialize_for_work_item(verification),
                )
            self.recovery.update(run_id, "complete_stage", stage="verify", result=verification)

            record_task = tasks[8]
            current = self.work_items.get_workflow(workflow_id)
            record_state = next(item for item in current["tasks"] if item["task_id"] == record_task["task_id"])
            if record_state["status"] == "pending":
                self.work_items.update_task(workflow_id, record_task["task_id"], "in_progress")
            if record_state["status"] != "completed":
                self.work_items.update_task(
                    workflow_id,
                    record_task["task_id"],
                    "completed",
                    result=self._serialize_for_work_item({"success": True, "resumed": True}),
                )
            self.recovery.update(run_id, "start_stage", stage="record")
            self.recovery.update(run_id, "complete_stage", stage="record", result={"workflow_id": workflow_id})
            self.recovery.update(run_id, "complete_run", last_completed_stage="record")
            return {
                "success": True,
                "state": "completed",
                "run_id": run_id,
                "workflow_id": workflow_id,
                "iteration": iteration_number,
                "validation": validation,
                "verification": verification,
                "workflow": self.work_items.get_workflow(workflow_id),
            }
        except ValueError as exc:
            return {
                "success": False,
                "state": "blocked",
                "code": "resume_limit_reached",
                "run_id": run_id,
                "message": str(exc),
            }

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