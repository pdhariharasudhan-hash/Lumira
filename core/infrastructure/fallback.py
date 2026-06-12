from typing import Any, Dict


def build_fallback_response(
    endpoint: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:

    result = {}

    if endpoint == "validate":

        result = {
            "idea": payload.get("input"),
            "weaknesses": [],
            "risks": [],
            "verdict": "continue",
            "risk_level": "low"
        }

    elif endpoint == "builder":

        result = {
            "objective": payload.get("input"),
            "scope": "small",
            "suggested_steps": [
                {
                    "id": "step_1",
                    "action": "create fastapi app instance",
                    "inputs": {},
                    "expected_output": "fastapi app initialized",
                    "dependencies": []
                },
                {
                    "id": "step_2",
                    "action": "define api route for task management",
                    "inputs": {},
                    "expected_output": "task route defined",
                    "dependencies": ["step_1"]
                }
            ],
            "status": "fallback"
        }

    elif endpoint == "execute":

        result = {
            "execution_order": [
                "step_1",
                "step_2"
            ],
            "today_task": "step_1",
            "task_steps": [
                "execute step_1"
            ],
            "expected_output": "step completed",
            "blockers": [],
            "status": "fallback"
        }

    elif endpoint == "code":

        result = {
            "idea": payload.get("input"),
            "code_target": "generated_app",
            "file_plan": [
                "main.py"
            ],
            "implementation_steps": [
                "create app"
            ],
            "test_steps": [
                "run app"
            ],
            "priority": "medium",
            "status": "fallback"
        }

    return {
        "status": "degraded",
        "error": f"{endpoint} backend unavailable",
        "degraded": True,
        "data": {
            "result": result
        }
    }