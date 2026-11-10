from __future__ import annotations

from typing import Any

from app.agents.agent_manager import AgentManager


class AgentCollaborationService:
    """Bounded structured collaboration over the existing agent manager."""

    MAX_MESSAGES = 8
    MAX_TASKS = 3

    def __init__(self, manager: AgentManager | None = None):
        self.manager = manager or AgentManager()

    def communicate(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(messages, list) or not 1 <= len(messages) <= self.MAX_MESSAGES:
            return {"success": False, "code": "invalid_message_count"}
        normalized = []
        for message in messages:
            if not isinstance(message, dict):
                return {"success": False, "code": "invalid_message"}
            sender = message.get("sender")
            recipient = message.get("recipient")
            content = message.get("content")
            if not all(isinstance(value, str) and value.strip() for value in (sender, recipient, content)):
                return {"success": False, "code": "invalid_message"}
            if len(content) > 5000:
                return {"success": False, "code": "message_too_large"}
            normalized.append({"sender": sender.strip(), "recipient": recipient.strip(), "content": content.strip()})
        return {"success": True, "messages": normalized, "count": len(normalized)}

    def collaborate(self, tasks: list[dict[str, str]]) -> dict[str, Any]:
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= self.MAX_TASKS:
            return {"success": False, "code": "invalid_task_count"}
        if any(not isinstance(task, dict) for task in tasks):
            return {"success": False, "code": "invalid_task"}
        results = []
        seen = set()
        for task in tasks:
            agent = task.get("agent")
            prompt = task.get("task")
            if not isinstance(agent, str) or not isinstance(prompt, str) or not prompt.strip():
                return {"success": False, "code": "invalid_task"}
            key = (agent, prompt.strip())
            if key in seen:
                return {"success": False, "code": "duplicate_task"}
            seen.add(key)
            result = self.manager.run(agent, prompt)
            results.append({"agent": agent, "task": prompt.strip(), "result": result})
            if result.get("success") is not True:
                return {"success": False, "state": "failed", "code": "agent_failed", "results": results}
        return {"success": True, "state": "completed", "results": results}

    @staticmethod
    def evaluate(results: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(results, list) or not results:
            return {"success": False, "code": "invalid_results"}
        accepted = []
        rejected = []
        for item in results:
            result = item.get("result") if isinstance(item, dict) else None
            if isinstance(result, dict) and result.get("success") is True:
                accepted.append(item)
            else:
                rejected.append(item)
        return {
            "success": not rejected,
            "accepted": len(accepted),
            "rejected": len(rejected),
            "results": accepted,
            "rejected_results": rejected,
        }

    @staticmethod
    def optimize(results: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize measurable outcomes for bounded agent allocation."""
        if not isinstance(results, list) or not results:
            return {"success": False, "code": "invalid_results"}
        by_agent: dict[str, dict[str, int]] = {}
        for item in results:
            if not isinstance(item, dict) or not isinstance(item.get("agent"), str):
                return {"success": False, "code": "invalid_result"}
            agent = item["agent"]
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            metrics = by_agent.setdefault(agent, {"runs": 0, "successes": 0, "failures": 0})
            metrics["runs"] += 1
            if result.get("success") is True:
                metrics["successes"] += 1
            else:
                metrics["failures"] += 1
        recommendations = [
            {
                "agent": agent,
                "success_rate": round(metrics["successes"] / metrics["runs"], 3),
                "recommendation": (
                    "retain allocation"
                    if metrics["successes"] == metrics["runs"]
                    else "investigate failures before increasing allocation"
                ),
            }
            for agent, metrics in sorted(by_agent.items())
        ]
        return {"success": True, "metrics": by_agent, "recommendations": recommendations}
