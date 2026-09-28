from typing import Any


class ExecuteService:
    """Validate an ordered builder plan and expose its execution readiness."""

    MAX_STEPS = 12

    def execute(self, idea: str, builder: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(builder, dict):
            return self._refine("builder result must be an object")
        if builder.get("status") != "accept":
            return self._refine("builder has not accepted the request", builder_status=builder.get("status"))
        steps = builder.get("suggested_steps")
        if not isinstance(steps, list) or not steps or len(steps) > self.MAX_STEPS:
            return self._refine(f"plan must contain 1 to {self.MAX_STEPS} steps")

        ids: list[str] = []
        for step in steps:
            if not isinstance(step, dict):
                return self._refine("every plan step must be an object")
            step_id = step.get("id")
            if not isinstance(step_id, str) or not step_id.strip() or step_id in ids:
                return self._refine("plan step identifiers must be unique non-empty strings")
            if not isinstance(step.get("action"), str) or not step["action"].strip():
                return self._refine("every plan step needs an actionable description")
            if not isinstance(step.get("expected_output"), str) or not step["expected_output"].strip():
                return self._refine("every plan step needs an expected output")
            dependencies = step.get("dependencies", [])
            if not isinstance(dependencies, list) or any(dependency not in ids for dependency in dependencies):
                return self._refine("dependencies must refer to earlier plan steps")
            ids.append(step_id)

        return {
            "execution_order": ids,
            "today_task": ids[0],
            "next_tasks": ids[1:],
            "task_steps": ids,
            "expected_output": steps[-1]["expected_output"],
            "blockers": [],
            "status": "accept",
            "current_stage": "execute",
            "last_completed_stage": "builder",
            "final_status": "planned",
            "retry_count": 0,
        }

    @staticmethod
    def _refine(reason: str, **details) -> dict[str, Any]:
        return {
            "execution_order": [],
            "today_task": None,
            "next_tasks": [],
            "task_steps": [],
            "expected_output": "",
            "blockers": [reason],
            "status": "refine",
            "current_stage": "execute",
            "last_completed_stage": None,
            "final_status": "stopped",
            "retry_count": 0,
            **details,
        }
