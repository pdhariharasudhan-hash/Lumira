import re
import time
import multiprocessing
from queue import Empty
from threading import BoundedSemaphore

from app.agents.agent_registry import AgentRegistry
from app.agents.code_agent import CodeAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.research_agent import ResearchAgent


def _execute_agent_process(agent, task, output):
    try:
        output.put({"ok": True, "result": agent.execute(task)})
    except BaseException as exc:
        output.put({"ok": False, "error_type": type(exc).__name__, "error": str(exc)})


class AgentManager:
    """Deterministic, bounded dispatcher for the locally available agents."""

    MAX_TASK_LENGTH = 10000
    MAX_CONCURRENT_AGENTS = 2
    _slots = BoundedSemaphore(MAX_CONCURRENT_AGENTS)

    def __init__(self, timeout_seconds: float = 30.0):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds
        self.registry = AgentRegistry()
        for agent in (CodeAgent(), PlannerAgent(), ResearchAgent()):
            self.register(agent)

    def register(self, agent):
        self.registry.register(agent)

    def run(self, agent_name: str, task: str):
        if not isinstance(task, str) or not task.strip():
            return {"success": False, "state": "rejected", "code": "invalid_task", "message": "Task must be a non-empty string."}
        if len(task) > self.MAX_TASK_LENGTH:
            return {"success": False, "state": "rejected", "code": "task_too_large", "message": f"Agent tasks are limited to {self.MAX_TASK_LENGTH} characters."}
        agent = self.registry.get(agent_name)
        if not agent:
            return {"success": False, "state": "rejected", "code": "agent_not_found", "message": "agent not found"}

        started = time.monotonic()
        if not self._slots.acquire(blocking=False):
            return {
                "success": False,
                "state": "rejected",
                "code": "agent_capacity_reached",
                "message": f"At most {self.MAX_CONCURRENT_AGENTS} agents may run at once.",
                "task": task.strip(),
                "retry_count": 0,
            }
        process = None
        output = None
        try:
            context = multiprocessing.get_context("spawn")
            output = context.Queue(maxsize=1)
            process = context.Process(
                target=_execute_agent_process,
                args=(agent, task.strip(), output),
                daemon=True,
            )
            process.start()
            try:
                # Drain the result while the child runs. Joining first can
                # deadlock when a valid generated-code result fills the pipe.
                outcome = output.get(timeout=self.timeout_seconds)
            except Empty:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                    return {
                        "success": False,
                        "state": "timed_out",
                        "code": "agent_timeout",
                        "agent": agent_name,
                        "task": task.strip(),
                        "timeout_seconds": self.timeout_seconds,
                        "retry_count": 0,
                        "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    }
                return {
                    "success": False,
                    "state": "failed",
                    "code": "agent_process_failed",
                    "agent": agent_name,
                    "task": task.strip(),
                    "exit_code": process.exitcode,
                    "retry_count": 0,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                }
            process.join(timeout=2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if not outcome["ok"]:
                return {
                    "success": False,
                    "state": "failed",
                    "agent": agent_name,
                    "task": task.strip(),
                    "error": {"type": outcome["error_type"], "message": outcome["error"]},
                    "retry_count": 0,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                }
            result = outcome["result"]
        except Exception as exc:
            return {
                "success": False,
                "state": "failed",
                "agent": agent_name,
                "task": task.strip(),
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "retry_count": 0,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            }
        finally:
            if process is not None and process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if output is not None:
                output.close()
            self._slots.release()
        succeeded = not (isinstance(result, dict) and result.get("success") is False)
        return {
            "success": succeeded,
            "state": result.get("status", "completed") if isinstance(result, dict) else "completed",
            "agent": agent_name,
            "capabilities": list(agent.capabilities),
            "task": task.strip(),
            "result": result,
            "retry_count": 0,
            "timeout_seconds": self.timeout_seconds,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }

    def dispatch(self, task: str):
        if not isinstance(task, str):
            return self.run("", task)
        task_lower = task.lower()
        if re.search(r"\b(build|create|generate|code|api|app|website)\b", task_lower):
            return self.run("code_agent", task)
        if re.search(r"\b(plan|planning|steps|roadmap)\b", task_lower):
            return self.run("planner_agent", task)
        if re.search(r"\b(research|find|analyze|investigate|learn|explain)\b", task_lower):
            return self.run("research_agent", task)
        return {"success": False, "state": "rejected", "code": "no_matching_agent", "message": "No registered agent capability matches this task."}

    def list_agents(self):
        return self.registry.list_agents()
