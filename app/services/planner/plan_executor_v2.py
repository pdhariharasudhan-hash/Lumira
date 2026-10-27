"""Bounded execution of explicitly registered planner step handlers.

This executor deliberately has no built-in success-only stub handlers. The
application must inject real capability handlers before a step can run.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


class PlanExecutorV2:
    """Execute a small plan in order and stop safely on the first failure."""

    MAX_STEPS = 12
    MAX_STEP_LENGTH = 200

    def __init__(self, handlers: Mapping[str, Callable[[], Any]] | None = None) -> None:
        self.handlers = dict(handlers or {})

    @staticmethod
    def _normalize_result(step: str, result: Any) -> dict[str, Any]:
        if hasattr(result, "to_dict") and callable(result.to_dict):
            result = result.to_dict()
        if not isinstance(result, dict) or type(result.get("success")) is not bool:
            return {
                "step": step,
                "success": False,
                "code": "invalid_handler_result",
                "message": "The step handler did not return a result with an explicit boolean success field.",
            }
        return {"step": step, **result}

    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(plan, dict):
            return {
                "success": False,
                "state": "rejected",
                "code": "invalid_plan",
                "message": "Plan must be an object.",
                "results": [],
            }

        raw_steps = plan.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            return {
                "success": False,
                "state": "blocked",
                "code": "empty_plan",
                "message": "No execution steps were supplied.",
                "goal": plan.get("goal"),
                "intent": plan.get("intent"),
                "results": [],
            }
        if len(raw_steps) > self.MAX_STEPS:
            return {
                "success": False,
                "state": "rejected",
                "code": "plan_too_large",
                "message": f"Plans are limited to {self.MAX_STEPS} steps.",
                "goal": plan.get("goal"),
                "intent": plan.get("intent"),
                "results": [],
            }

        results: list[dict[str, Any]] = []
        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, str) or not raw_step.strip() or len(raw_step) > self.MAX_STEP_LENGTH:
                result = {
                    "step": str(raw_step)[: self.MAX_STEP_LENGTH],
                    "success": False,
                    "code": "invalid_step",
                    "message": "Each step must be a non-empty string within the configured length limit.",
                }
                results.append(result)
                return {
                    "success": False,
                    "state": "failed",
                    "code": result["code"],
                    "goal": plan.get("goal"),
                    "intent": plan.get("intent"),
                    "completed_steps": index,
                    "failed_step": result["step"],
                    "blocked_steps": len(raw_steps) - index - 1,
                    "results": results,
                }

            step = raw_step.strip()
            handler = self.handlers.get(step)
            if not callable(handler):
                result = {
                    "step": step,
                    "success": False,
                    "code": "handler_not_registered",
                    "message": "No real capability handler is registered for this step; execution stopped.",
                }
            else:
                try:
                    result = self._normalize_result(step, handler())
                except Exception as exc:
                    result = {
                        "step": step,
                        "success": False,
                        "code": "handler_execution_failed",
                        "error_type": type(exc).__name__,
                        "message": "The step handler raised an exception; downstream steps were not executed.",
                    }

            results.append(result)
            if result.get("success") is not True:
                return {
                    "success": False,
                    "state": "failed",
                    "code": result.get("code", "step_failed"),
                    "goal": plan.get("goal"),
                    "intent": plan.get("intent"),
                    "completed_steps": index,
                    "failed_step": step,
                    "blocked_steps": len(raw_steps) - index - 1,
                    "results": results,
                }

        return {
            "success": True,
            "state": "completed",
            "goal": plan.get("goal"),
            "intent": plan.get("intent"),
            "completed_steps": len(results),
            "blocked_steps": 0,
            "results": results,
        }
