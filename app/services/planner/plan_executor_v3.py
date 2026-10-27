"""Bounded project-planning pipeline.

This module generates and validates a project plan and code artifacts. It does
not run generated code. Every stage must explicitly accept its input before
the next stage can begin.
"""
from __future__ import annotations

from typing import Any

from app.services.builder.builder_service import BuilderService
from app.services.execution.execute_service import ExecuteService
from app.services.execution.execution_session_service import ExecutionSessionService
from app.services.code.code_service import CodeService


class PlanExecutorV3:
    MAX_GOAL_LENGTH = 10_000

    @staticmethod
    def _blocked(stage: str, code: str, message: str, **details: Any) -> dict[str, Any]:
        return {
            "success": False,
            "state": "blocked",
            "code": code,
            "message": message,
            "current_stage": stage,
            "last_completed_stage": None,
            "execution_mode": "planning_only",
            **details,
        }

    @staticmethod
    def _accepted(result: Any) -> bool:
        return isinstance(result, dict) and result.get("status") == "accept"

    def execute(self, goal: str) -> dict[str, Any]:
        if not isinstance(goal, str) or not goal.strip() or len(goal) > self.MAX_GOAL_LENGTH:
            return self._blocked(
                "input",
                "invalid_goal",
                f"Goal must contain 1 to {self.MAX_GOAL_LENGTH} characters.",
            )
        goal = goal.strip()

        try:
            builder = BuilderService().build(goal)
        except Exception as exc:
            return self._blocked(
                "builder",
                "builder_failed",
                "The builder failed; downstream stages were not started.",
                error_type=type(exc).__name__,
            )
        if not self._accepted(builder):
            return self._blocked(
                "builder",
                "builder_rejected",
                "The builder did not accept the goal; execution planning and code generation were stopped.",
                builder=builder if isinstance(builder, dict) else None,
            )

        try:
            execution = ExecuteService().execute(goal, builder)
        except Exception as exc:
            return self._blocked(
                "execute",
                "planning_failed",
                "Execution-plan validation failed; code generation was not started.",
                error_type=type(exc).__name__,
                builder=builder,
                last_completed_stage="builder",
            )
        if not self._accepted(execution):
            return self._blocked(
                "execute",
                "plan_rejected",
                "The execution plan was not accepted; code generation was stopped.",
                builder=builder,
                execution=execution if isinstance(execution, dict) else None,
                last_completed_stage="builder",
            )

        try:
            code = CodeService().generate(goal, execution)
        except Exception as exc:
            return self._blocked(
                "code",
                "code_generation_failed",
                "Code generation failed; no completion was reported.",
                error_type=type(exc).__name__,
                builder=builder,
                execution=execution,
                last_completed_stage="execute",
            )
        if not self._accepted(code):
            return self._blocked(
                "code",
                "code_generation_rejected",
                "Code generation did not accept the validated plan.",
                builder=builder,
                execution=execution,
                generated_code=code if isinstance(code, dict) else None,
                last_completed_stage="execute",
            )

        try:
            session = ExecutionSessionService().create_session(goal, builder, execution, code)
        except Exception as exc:
            return {
                "success": False,
                "state": "failed",
                "code": "session_persistence_failed",
                "message": "Planning and code generation completed, but the execution session could not be saved.",
                "current_stage": "session",
                "last_completed_stage": "code",
                "execution_mode": "planning_only",
                "builder": builder,
                "execution": execution,
                "generated_code": code,
                "error_type": type(exc).__name__,
            }
        if not isinstance(session, dict) or session.get("success") is False:
            return {
                "success": False,
                "state": "failed",
                "code": "session_persistence_failed",
                "message": "Planning and code generation completed, but session persistence did not return a valid result.",
                "current_stage": "session",
                "last_completed_stage": "code",
                "execution_mode": "planning_only",
                "builder": builder,
                "execution": execution,
                "generated_code": code,
                "session": session if isinstance(session, dict) else None,
            }

        return {
            "success": True,
            "state": "completed",
            "goal": goal,
            "current_stage": "completed",
            "last_completed_stage": "session",
            "execution_mode": "planning_only",
            "session": session,
            "builder": builder,
            "execution": execution,
            "code": code,
        }
