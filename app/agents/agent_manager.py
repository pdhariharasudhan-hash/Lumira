import re
import time
import multiprocessing
from queue import Empty
from threading import BoundedSemaphore

from app.agents.agent_registry import AgentRegistry
from app.agents.code_agent import CodeAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.research_agent import ResearchAgent
from app.services.resources.resource_budget_service import ResourceBudgetService


def _execute_agent_process(agent, task, output):
    try:
        output.put({"ok": True, "result": agent.execute(task)})
    except BaseException as exc:
        # Exception text may contain local paths, credentials, or prompt data.
        # Keep only the type for diagnostics; never return raw child exceptions.
        output.put({"ok": False, "error_type": type(exc).__name__})


class AgentManager:
    """Deterministic, bounded dispatcher for the locally available agents."""

    MAX_TASK_LENGTH = 10000
    # Lumira's current target host has 8 GiB RAM. Keep direct callers bounded
    # to one child process as well as the higher-level orchestrator path.
    MAX_CONCURRENT_AGENTS = 1
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

        # Direct AgentManager callers receive the same critical-RAM guard as
        # orchestrated calls; telemetry failure must never block normal work.
        try:
            resource_state = ResourceBudgetService().snapshot()
            if resource_state.get("resource_pressure") == "critical":
                return {
                    "success": False,
                    "state": "deferred",
                    "code": "resource_pressure_critical",
                    "message": "Agent execution is deferred because available system memory is critically low.",
                    "agent": agent_name,
                    "retry_count": 0,
                    "resource_pressure": "critical",
                }
        except Exception:
            pass

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
                    "error": {
                        "type": outcome["error_type"],
                        "message": "Agent execution failed; internal details were withheld.",
                    },
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
                "error": {
                    "type": type(exc).__name__,
                    "message": "Agent execution failed; internal details were withheld.",
                },
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
        if not isinstance(result, dict):
            return {
                "success": False,
                "state": "failed",
                "code": "invalid_agent_result",
                "message": "Agent returned a non-object result; it was not accepted as successful.",
                "agent": agent_name,
                "task": task.strip(),
                "retry_count": 0,
                "timeout_seconds": self.timeout_seconds,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            }

        # Keep the legacy default for structured results that omit success,
        # but reject truthy non-boolean values such as 1 or "false".
        succeeded = result.get("success", True) is True
        state = result.get("status", "completed" if succeeded else "failed")
        if not succeeded and state == "completed":
            state = "failed"
        return {
            "success": succeeded,
            "state": state,
            "agent": agent_name,
            "capabilities": list(agent.capabilities),
            "task": task.strip(),
            "result": result,
            "retry_count": 0,
            "timeout_seconds": self.timeout_seconds,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }

    def select_agent(self, task: str) -> dict:
        """Recommend one registered agent without starting a process.

        Selection is deterministic and intentionally side-effect free so the
        primary command route can expose agent guidance without duplicating
        capability execution.
        """
        if not isinstance(task, str) or not task.strip():
            return {
                "success": False,
                "selected_agent": None,
                "reason": "invalid_task",
                "available_agents": self.list_agents(),
            }
        normalized = " ".join(task.casefold().split())
        families = (
            ("research_agent", (
                r"\b(research|compare|comparison|versus|vs|investigate|analy[sz]e|analysis|evidence|summari[sz]e|extract knowledge|market research|technical research|document research|knowledge retrieval|find sources|gather sources|fact check|fact-check)\b",
            )),
            ("planner_agent", (
                r"\b(plan|planning|steps|roadmap|prioriti[sz]e|break down|decompose|milestone|schedule|sequence tasks|goal)\b",
            )),
            ("code_agent", (
                r"\b(debug|fix|repair|refactor|implement|code|api|app|website|software|program|script|compile|syntax error|bug|patch|generate files)\b",
            )),
        )
        for agent_name, patterns in families:
            if any(re.search(pattern, normalized) for pattern in patterns):
                return {
                    "success": True,
                    "selected_agent": agent_name,
                    "reason": "deterministic_capability_match",
                    "available_agents": self.list_agents(),
                }
        return {
            "success": False,
            "selected_agent": None,
            "reason": "no_matching_agent",
            "available_agents": self.list_agents(),
        }

    def dispatch(self, task: str):
        if not isinstance(task, str):
            return self.run("", task)
        normalized = " ".join(task.casefold().split())
        if not normalized:
            return self.run("research_agent", task)

        # Specific intent families must be checked before broad verbs such as
        # "create" or "build", otherwise "create a research comparison" would
        # be incorrectly sent to the code agent.
        recommendation = self.select_agent(task)
        selected = recommendation.get("selected_agent")
        if selected:
            return self.run(selected, task)
        return {
            "success": False,
            "state": "rejected",
            "code": "no_matching_agent",
            "message": "No registered agent capability matches this task.",
            "available_agents": recommendation.get("available_agents", self.list_agents()),
        }

    def list_agents(self):
        return self.registry.list_agents()
