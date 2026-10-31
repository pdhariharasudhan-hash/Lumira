"""Gate bounded agent execution on Lumira's primary cognitive pipeline.

The general command route can pass its already-validated brain response to
execute_after_brain(), avoiding duplicate brain execution and side effects.
"""
from app.agents.agent_manager import AgentManager
from app.services.brain.brain_request import BrainRequest
from app.services.brain.brain_service import BrainService
from app.services.sessions.session_manager_service import redact_sensitive_text
from app.services.resources.resource_budget_service import ResourceBudgetService
from threading import Lock


class BrainAgentOrchestrator:
    """Gate explicit agent execution on successful primary-brain processing."""

    # Serialize agent dispatch on the low-memory desktop profile. This is an
    # actual in-process gate, unlike the advisory limits exposed by the API.
    _dispatch_lock = Lock()

    def __init__(self, brain_service=None, agent_manager=None):
        # Keep construction lazy: the /command route already ran the brain and
        # should not construct a second BrainService just to dispatch an agent.
        self.brain_service = brain_service
        self.agent_manager = agent_manager

    def validate_request(self, task: str, agent_name: str | None = None) -> dict | None:
        """Validate agent task bounds and names before the main brain runs."""
        return self._preflight(task, agent_name)

    def _preflight(self, task: str, agent_name: str | None = None) -> dict | None:
        if not isinstance(task, str) or not task.strip():
            return {
                "success": False, "state": "rejected", "code": "invalid_task",
                "message": "Task must be a non-empty string.",
            }
        if self.agent_manager is None:
            self.agent_manager = AgentManager()
        max_length = getattr(self.agent_manager, "MAX_TASK_LENGTH", 10000)
        if len(task) > max_length:
            return {
                "success": False, "state": "rejected", "code": "task_too_large",
                "message": f"Agent tasks are limited to {max_length} characters.",
            }
        registry = getattr(self.agent_manager, "registry", None)
        if agent_name and registry is not None and not registry.exists(agent_name):
            return {
                "success": False, "state": "rejected", "code": "agent_not_found",
                "message": "agent not found",
            }
        return None

    def execute(self, task: str, agent_name: str | None = None, session_id: str | None = None, project_id: str | None = None, goal_id: str | None = None) -> dict:
        rejected = self._preflight(task, agent_name)
        if rejected:
            return rejected

        if self.brain_service is None:
            self.brain_service = BrainService()
        metadata = {}\n        try:\n            from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService\n            metadata["core_context"] = CoreRuntimeBridgeService().context(session_id, project_id, goal_id).get("context", {})\n        except Exception:\n            metadata = {}\n        brain = self.brain_service.execute(BrainRequest(message=task.strip(), session_id=session_id or "", project=project_id or "", metadata=metadata))
        return self.execute_after_brain(task, brain, agent_name=agent_name)

    def execute_after_brain(self, task: str, brain_response, agent_name: str | None = None, core_context: dict | None = None) -> dict:
        """Dispatch only after the caller's primary-brain pass succeeded."""
        rejected = self._preflight(task, agent_name)
        if rejected:
            return rejected
        # Only a literal boolean success may authorize downstream agent execution.
        # Truthy strings/integers are malformed and must fail closed.
        if getattr(brain_response, "success", False) is not True:
            error = getattr(brain_response, "error", None)
            return {
                "success": False,
                "state": "failed",
                "code": "brain_validation_failed",
                "message": "Lumira's main brain could not validate this task; agent execution was not started.",
                "brain": {
                    "success": False,
                    "error": redact_sensitive_text(error or "Brain validation failed."),
                },
            }

        task = task.strip()
        try:
            resource_snapshot = ResourceBudgetService().snapshot()
            pressure = resource_snapshot.get("resource_pressure", "unknown")
        except Exception:
            pressure = "unknown"

        if pressure == "critical":
            return {
                "success": False,
                "state": "deferred",
                "code": "resource_pressure_critical",
                "message": "Agent dispatch was deferred because available system memory is critically low. Close unused applications and retry.",
                "orchestration": {"brain_gate": "passed", "agent_execution_started": False},
            }

        if not self._dispatch_lock.acquire(blocking=False):
            return {
                "success": False,
                "state": "deferred",
                "code": "agent_capacity_busy",
                "message": "Another agent task is already running. On this memory-constrained host, Lumira runs agent tasks one at a time; retry after it finishes.",
                "orchestration": {"brain_gate": "passed", "agent_execution_started": False},
            }

        try:
            result = (
                self.agent_manager.run(agent_name, task)
                if agent_name
                else self.agent_manager.dispatch(task)
            )
        except Exception as exc:
            return {
                "success": False,
                "state": "failed",
                "code": "agent_dispatch_failed",
                "message": "The agent manager failed before returning a valid result.",
                "error_type": type(exc).__name__,
            }
        finally:
            self._dispatch_lock.release()
        if not isinstance(result, dict):
            return {
                "success": False,
                "state": "failed",
                "code": "invalid_agent_result",
                "message": "The agent manager returned an invalid result; orchestration stopped safely.",
            }
        state = getattr(brain_response, "state", None)
        execution_context = getattr(state, "execution_context", None)
        agent_state = result.get("state")
        normalized_agent_state = agent_state.strip().lower() if isinstance(agent_state, str) else ""
        result["core_context"] = core_context or getattr(getattr(brain_response, "state", None), "execution_context", None).metadata.get("core_context", {}) if getattr(getattr(brain_response, "state", None), "execution_context", None) else (core_context or {})\n        result["orchestration"] = {
            "brain_gate": "passed",
            "brain_execution_id": getattr(execution_context, "execution_id", None),
            "brain_last_completed_stage": getattr(state, "last_completed_stage", None),
            # Only states that positively indicate a launched/running/completed
            # execution count as started. Generic failure is ambiguous (for example,
            # process creation can fail before the agent begins), so fail closed.
            "agent_execution_started": normalized_agent_state in {
                "started", "running", "in_progress", "in-progress", "working",
                "executing", "timed_out", "completed",
            },
        }
        return result
