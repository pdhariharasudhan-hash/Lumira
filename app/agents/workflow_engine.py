import json
import multiprocessing
from multiprocessing.queues import Empty
from threading import BoundedSemaphore, Lock
import time

from app.agents.planner_agent import PlannerAgent
from app.agents.workflow_step_router import WorkflowStepRouter
from app.services.sessions.session_manager_service import SessionManagerService, redact_sensitive_value
from app.services.workflow_recovery.run_recovery_service import (
    RunRecoveryService,
    SIDE_EFFECT_STAGES,
)


def _workflow_stage_worker(step, goal, context, output):
    try:
        result = WorkflowStepRouter().execute_step(step, goal, context)
        output.put({"ok": True, "result": result})
    except BaseException as exc:
        output.put({"ok": False, "error_type": type(exc).__name__, "error": str(exc)})


class WorkflowEngine:
    """Bounded allowlisted workflow execution with durable stage checkpoints."""

    MAX_STEPS = 12
    MAX_GOAL_LENGTH = 10_000
    ALLOWED_STEPS = {
        "validate", "builder", "execute", "code", "save_project", "search",
        "generate_image", "save_artifact", "capture_audio", "transcribe", "summarize",
    }
    DEFAULT_STAGE_TIMEOUT_SECONDS = 30.0
    MAX_CONCURRENT_CAPABILITIES = 2
    _slots = BoundedSemaphore(MAX_CONCURRENT_CAPABILITIES)
    _active_processes = {}
    _cancelled_runs = set()
    _process_lock = Lock()

    def __init__(self, planner=None, router=None, recovery=None, timeout_seconds: float = DEFAULT_STAGE_TIMEOUT_SECONDS, worker_target=None):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.planner = planner or PlannerAgent()
        self.isolated = router is None
        self.router = router or WorkflowStepRouter()
        self.recovery = recovery or RunRecoveryService()
        self.timeout_seconds = timeout_seconds
        self.worker_target = worker_target or _workflow_stage_worker

    @classmethod
    def cancel(cls, run_id: str) -> bool:
        with cls._process_lock:
            process = cls._active_processes.get(run_id)
            if process is None or not process.is_alive():
                return False
            cls._cancelled_runs.add(run_id)
            process.terminate()
            return True

    def execute(self, goal: str, session_id: str | None = None):
        if not isinstance(goal, str) or not goal.strip() or len(goal) > self.MAX_GOAL_LENGTH:
            return {"success": False, "state": "rejected", "code": "invalid_goal", "message": "Goal must contain 1 to 10000 characters."}
        plan = self.planner.execute(goal)
        if not isinstance(plan, dict) or not plan.get("success", False):
            return {"success": False, "message": "planning failed", "plan": plan}
        steps = plan.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= self.MAX_STEPS:
            return {"success": False, "state": "rejected", "code": "invalid_plan", "message": f"Workflow plans must contain 1 to {self.MAX_STEPS} steps.", "plan": plan}
        unsupported = [step for step in steps if not isinstance(step, str) or step not in self.ALLOWED_STEPS]
        if unsupported:
            return {"success": False, "state": "rejected", "code": "capability_unavailable", "unsupported_steps": unsupported, "plan": plan}
        run = self.recovery.create_run(goal, plan, session_id)
        return self._continue(run, plan, {}, [])

    def resume(self, run_id: str):
        run = self.recovery.get_run(run_id)
        if run is None:
            return {"success": False, "state": "rejected", "code": "run_not_found", "run_id": run_id}
        if run.get("status") == "completed":
            return {"success": False, "state": "rejected", "code": "run_already_completed", "run_id": run_id}
        if run.get("status") == "blocked":
            return {"success": False, "state": "blocked", "code": "manual_reconciliation_required", "run_id": run_id, "recovery": run}
        if not run.get("resume_allowed", True):
            self.recovery.update(run_id, "block", error="side_effect_outcome_unknown_reconcile_before_resume")
            return {"success": False, "state": "blocked", "code": "manual_reconciliation_required", "run_id": run_id}
        session_id = run.get("session_id")
        if session_id:
            session = SessionManagerService().get_session(session_id)
            if session is None:
                return {"success": False, "state": "rejected", "code": "session_not_found", "run_id": run_id}
            if session.get("status") == "closed":
                return {"success": False, "state": "rejected", "code": "session_closed", "run_id": run_id}
        plan = run.get("plan")
        steps = plan.get("steps") if isinstance(plan, dict) else None
        if not isinstance(steps, list) or not 1 <= len(steps) <= self.MAX_STEPS or any(not isinstance(step, str) or step not in self.ALLOWED_STEPS for step in steps):
            self.recovery.update(run_id, "block", error="persisted_plan_invalid")
            return {"success": False, "state": "blocked", "code": "persisted_plan_invalid", "run_id": run_id}
        current_record = next(
            (item for item in run.get("stage_records", []) if item.get("stage") == run.get("current_stage")),
            None,
        )
        if current_record and current_record.get("stage") in SIDE_EFFECT_STAGES and current_record.get("status") in {"running", "failed"}:
            self.recovery.update(run_id, "block", error="side_effect_outcome_unknown_reconcile_before_resume")
            return {"success": False, "state": "blocked", "code": "manual_reconciliation_required", "run_id": run_id}

        completed = {item["stage"]: item.get("result") for item in run.get("stage_records", []) if item.get("status") == "completed"}
        context = {stage: value for stage, value in completed.items()}
        results = [completed[step] for step in steps if step in completed]
        try:
            self.recovery.update(run_id, "resume")
        except ValueError:
            return {"success": False, "state": "blocked", "code": "resume_limit_reached", "run_id": run_id}
        return self._continue(run, plan, context, results)

    def inspect(self, run_id: str):
        return self.recovery.get_run(run_id)

    def _continue(self, run: dict, plan: dict, context: dict, results: list):
        goal = run["goal"]
        run_id = run["run_id"]
        completed = {item["stage"] for item in run.get("stage_records", []) if item.get("status") == "completed"}
        try:
            for step in plan["steps"]:
                if step in completed:
                    continue
                self.recovery.update(run_id, "start_stage", stage=step)
                try:
                    result = self._execute_stage(run_id, step, goal, context)
                except Exception as exc:
                    safe_error = redact_sensitive_value({"type": type(exc).__name__, "message": str(exc)})
                    self.recovery.update(run_id, "fail_stage", stage=step, error=str(safe_error))
                    return {
                        "success": False, "state": "failed", "code": "capability_execution_failed",
                        "goal": goal, "run_id": run_id, "failed_step": step,
                        "failure": safe_error, "plan": plan, "results": results,
                        "current_stage": step, "last_completed_stage": self.recovery.get_run(run_id).get("last_completed_stage"),
                    }
                safe_result = redact_sensitive_value(result)
                stage_rejected = step in {"builder", "execute", "code"} and isinstance(result, dict) and result.get("status") != "accept"
                failed = isinstance(result, dict) and (result.get("success") is False or stage_rejected)
                if failed:
                    self.recovery.update(run_id, "fail_stage", stage=step, error=str(safe_result.get("error") or safe_result.get("message") or safe_result.get("code") or "stage_failed"))
                    return {
                        "success": False, "state": "failed", "goal": goal, "run_id": run_id,
                        "failed_step": step, "failure": safe_result, "plan": redact_sensitive_value(plan), "results": results,
                        "context": redact_sensitive_value(context), "current_stage": step,
                        "last_completed_stage": self.recovery.get_run(run_id).get("last_completed_stage"),
                    }
                context[step] = result
                results.append(safe_result)
                self.recovery.update(run_id, "complete_stage", stage=step, result=safe_result)
            last_completed = plan["steps"][-1]
            run = self.recovery.update(run_id, "complete_run", last_completed_stage=last_completed)
        except Exception as exc:
            current = self.recovery.get_run(run_id)
            return {
                "success": False,
                "state": "failed",
                "code": "recovery_persistence_failed",
                "run_id": run_id,
                "current_stage": current.get("current_stage") if current else None,
                "last_completed_stage": current.get("last_completed_stage") if current else None,
                "message": "Workflow checkpoint persistence failed safely; inspect recovery state before resuming.",
            }
        return {
            "success": True,
            "goal": goal,
            "plan": redact_sensitive_value(plan),
            "results": results,
            "context": redact_sensitive_value(context),
            "run_id": run_id,
            "state": "completed",
            "current_stage": None,
            "last_completed_stage": run.get("last_completed_stage"),
            "retry_count": run.get("retry_count", 0),
        }

    def _execute_stage(self, run_id: str, step: str, goal: str, context: dict):
        if not self.isolated:
            return self.router.execute_step(step, goal, context)
        try:
            if len(json.dumps(context, ensure_ascii=False, default=str)) > RunRecoveryService.MAX_RESULT_CHARS:
                return {"success": False, "code": "capability_input_too_large", "message": "Workflow context exceeds the execution limit."}
        except (TypeError, ValueError, RecursionError):
            return {"success": False, "code": "invalid_capability_input", "message": "Workflow context is not serializable."}
        if not self._slots.acquire(blocking=False):
            return {"success": False, "code": "capability_capacity_reached", "message": "At most two capabilities may execute concurrently."}
        process = None
        output = None
        started = time.monotonic()
        try:
            multiprocessing_context = multiprocessing.get_context("spawn")
            output = multiprocessing_context.Queue(maxsize=1)
            process = multiprocessing_context.Process(
                target=self.worker_target,
                args=(step, goal, context, output),
                daemon=True,
            )
            process.start()
            with self._process_lock:
                self._active_processes[run_id] = process
            outcome = None
            while time.monotonic() - started < self.timeout_seconds:
                with self._process_lock:
                    cancelled = run_id in self._cancelled_runs
                if cancelled:
                    if process.is_alive():
                        process.terminate()
                    return {"success": False, "code": "capability_cancelled", "message": "Capability execution was cancelled."}
                try:
                    outcome = output.get(timeout=0.1)
                    break
                except Empty:
                    if not process.is_alive():
                        break
            if outcome is None:
                timed_out = time.monotonic() - started >= self.timeout_seconds and run_id not in self._cancelled_runs
                if process.is_alive():
                    process.terminate()
                process.join(timeout=2)
                return {
                    "success": False,
                    "code": "capability_timeout" if timed_out else "capability_cancelled" if run_id in self._cancelled_runs else "capability_process_failed",
                    "message": "Capability execution timed out and was terminated." if timed_out else "Capability execution did not return a result.",
                    "timeout_seconds": self.timeout_seconds if timed_out else None,
                }
            process.join(timeout=1)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if not outcome.get("ok"):
                return {"success": False, "code": "capability_execution_failed", "error": {"type": outcome.get("error_type"), "message": outcome.get("error")}}
            result = outcome.get("result")
            if len(json.dumps(result, ensure_ascii=False, default=str)) > RunRecoveryService.MAX_RESULT_CHARS:
                return {"success": False, "code": "capability_result_too_large", "message": "Capability result exceeds the persistence limit."}
            return result
        except Exception as exc:
            return {"success": False, "code": "capability_process_failed", "error": {"type": type(exc).__name__, "message": str(exc)}}
        finally:
            if process is not None and process.is_alive():
                process.terminate()
                process.join(timeout=2)
            with self._process_lock:
                self._active_processes.pop(run_id, None)
                self._cancelled_runs.discard(run_id)
            if output is not None:
                output.close()
            self._slots.release()
