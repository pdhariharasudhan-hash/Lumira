from typing import Any

from app.services.sessions.session_manager_service import redact_sensitive_text


def public_brain_state(state: Any) -> dict | None:
    if state is None:
        return None
    data = state.model_dump(mode="json") if hasattr(state, "model_dump") else state
    if not isinstance(data, dict):
        return None
    execution = data.get("execution_context") or {}
    goal = data.get("goal") or {}
    objective = data.get("objective") or {}
    mode = data.get("mode") or {}
    verification = data.get("verification") or {}
    reflection = data.get("reflection") or {}
    return {
        "execution_context": {
            "execution_id": execution.get("execution_id"),
            "request_id": execution.get("request_id"),
            "session_id": execution.get("session_id"),
            "project_id": execution.get("project_id"),
            "stage": execution.get("stage"),
        },
        "mode": {"active_mode": mode.get("active_mode")},
        "goal": {
            "primary_goal": redact_sensitive_text(str(goal.get("primary_goal") or "")),
            "confidence": goal.get("confidence"),
        },
        "objective": {
            "primary_objective": redact_sensitive_text(str(objective.get("primary_objective") or "")),
        },
        "verification": {
            "ready_for_execution": bool(verification.get("ready_for_execution")),
        },
        "reflection": {
            "overall_quality": reflection.get("overall_quality"),
            "confidence": reflection.get("confidence"),
        },
    }


def public_brain_trace(trace: Any) -> list[dict]:
    if not isinstance(trace, list):
        return []
    allowed = ("module", "order", "status", "attempt", "recovery", "recovery_status")
    result = []
    for entry in trace:
        if not isinstance(entry, dict):
            continue
        result.append({key: entry[key] for key in allowed if key in entry})
    return result
