from __future__ import annotations

from typing import Any

from app.agents.planner_agent import PlannerAgent


class DevelopmentPlanner:
    """
    Development-specific planning adapter.

    The existing PlannerAgent remains the reasoning source, but its
    general-purpose workflow output is validated and normalized for
    repository development.
    """

    MAX_STEPS = 8

    DEVELOPMENT_STEPS = {
        "inspect",
        "plan",
        "implement",
        "test",
        "diagnose",
        "fix",
        "verify",
    }

    REQUIRED_STEPS = {
        "inspect",
        "plan",
        "implement",
        "test",
        "verify",
    }

    def __init__(self, planner: PlannerAgent | None = None) -> None:
        self.planner = planner or PlannerAgent()

    def create_plan(
        self,
        goal: str,
        workspace: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("Development goal cannot be empty.")

        if not isinstance(workspace, dict):
            raise ValueError("Workspace inspection must be a dictionary.")

        prompt = self._build_prompt(goal, workspace)
        result = self.planner.execute(prompt)

        if not isinstance(result, dict):
            return self._fallback_plan(goal, "invalid_planner_result")

        if result.get("success") is False:
            return self._fallback_plan(
                goal,
                str(
                    result.get("message")
                    or result.get("error")
                    or "planner_failed"
                ),
            )

        steps = result.get("steps")

        if not isinstance(steps, list):
            return self._fallback_plan(
                goal,
                "planner_returned_invalid_steps",
            )

        normalized = self._normalize_steps(steps)

        if not self._is_valid_development_plan(normalized):
            return self._fallback_plan(
                goal,
                "planner_plan_not_suitable_for_development",
            )

        return {
            "success": True,
            "goal": goal.strip(),
            "steps": normalized,
            "planner_result": result,
        }

    def _normalize_steps(self, steps: list[Any]) -> list[str]:
        normalized: list[str] = []

        aliases = {
            "search": "inspect",
            "research": "inspect",
            "builder": "plan",
            "code": "implement",
            "execute": "implement",
            "validation": "test",
            "verification": "verify",
        }

        for step in steps:
            if not isinstance(step, str):
                continue

            value = step.strip().lower()

            if value in aliases:
                value = aliases[value]

            if value in self.DEVELOPMENT_STEPS and value not in normalized:
                normalized.append(value)

        return normalized[: self.MAX_STEPS]

    def _is_valid_development_plan(self, steps: list[str]) -> bool:
        if not steps:
            return False

        if not self.REQUIRED_STEPS.issubset(set(steps)):
            return False

        positions = {step: steps.index(step) for step in steps}

        return (
            positions["inspect"] < positions["plan"]
            < positions["implement"]
            < positions["test"]
            < positions["verify"]
        )

    def _fallback_plan(
        self,
        goal: str,
        reason: str,
    ) -> dict[str, Any]:
        """
        Safe deterministic fallback.

        This does not invent implementation details. It establishes only
        the mandatory development lifecycle.
        """

        return {
            "success": True,
            "goal": goal.strip(),
            "steps": [
                "inspect",
                "plan",
                "implement",
                "test",
                "diagnose",
                "fix",
                "verify",
            ],
            "planner_result": {
                "success": True,
                "fallback": True,
                "reason": reason,
            },
        }

    @staticmethod
    def _build_prompt(
        goal: str,
        workspace: dict[str, Any],
    ) -> str:
        file_count = workspace.get("file_count", 0)

        important_files = [
            path
            for path in workspace.get("files", [])
            if path.startswith(
                ("app/", "tests/", "lumira_desktop/")
            )
        ][:150]

        return (
            "You are planning a bounded repository-development task for Lumira.\n\n"
            f"DEVELOPMENT GOAL:\n{goal.strip()}\n\n"
            f"WORKSPACE FILE COUNT:\n{file_count}\n\n"
            "IMPORTANT WORKSPACE FILES:\n"
            + "\n".join(important_files)
            + "\n\n"
            "Return a JSON object with:\n"
            '{\n'
            '  "success": true,\n'
            '  "steps": ["inspect", "plan", "implement", "test", "verify"]\n'
            '}\n\n'
            "Development steps must come from:\n"
            "inspect, plan, implement, test, diagnose, fix, verify.\n\n"
            "The ordered lifecycle must begin with inspect, then plan, "
            "then implement, then test, and finish with verify.\n"
            "Use diagnose and fix only when needed.\n"
            "Do not return search as the complete development plan.\n"
            "Do not include shell commands.\n"
            "Do not access credentials or secrets.\n"
            "Do not modify .env or .git contents.\n"
            "Do not use git reset, git clean, or force push.\n"
            "Keep the plan bounded."
        )
