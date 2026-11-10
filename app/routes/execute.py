from typing import Dict, Any
import json

from fastapi import APIRouter
from pydantic import BaseModel, Field, StrictBool, field_validator

from app.services.execution.execute_service import ExecuteService
from app.services.response.response_service import (
    build_structured_response
)
from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
from app.services.persistence.atomic_json_store import PersistenceIntegrityError

router = APIRouter()

execute_service = ExecuteService()


def analyze_execution_request(content: str, builder: Dict[str, Any] | None = None) -> Dict[str, Any]:
    text = (content or "").strip()
    builder_payload = builder or {"suggested_steps": []}

    if not text:
        return {
            "execution_order": [],
            "today_task": None,
            "task_steps": [],
            "expected_output": "nothing generated",
            "blockers": ["no input provided"],
            "status": "refine"
        }

    result = execute_service.execute(text, builder_payload)

    if not validate_execute_output(result):
        return {
            "execution_order": [],
            "today_task": None,
            "task_steps": [],
            "expected_output": "",
            "blockers": ["Execution service returned an invalid plan."],
            "status": "refine",
        }

    return result


class ExecuteRequest(BaseModel):
    input: str = Field(max_length=10000)
    builder: Dict[str, Any]
    autonomous: StrictBool = False

    @field_validator("builder")
    @classmethod
    def builder_payload_is_bounded(cls, value):
        if len(json.dumps(value, ensure_ascii=False)) > 200_000:
            raise ValueError("builder payload exceeds 200000 characters")
        return value


def validate_execute_output(
    result: Dict[str, Any]
) -> bool:

    execution_order = result.get(
        "execution_order"
    )

    today_task = result.get(
        "today_task"
    )

    task_steps = result.get(
        "task_steps"
    )

    expected_output = result.get(
        "expected_output"
    )

    blockers = result.get(
        "blockers"
    )

    status = result.get(
        "status"
    )

    if not isinstance(
        execution_order,
        list
    ):
        return False

    if status not in [
        "accept",
        "refine",
        "reject"
    ]:
        return False

    if not isinstance(task_steps, list) or not isinstance(blockers, list):
        return False

    if status == "accept":
        if not execution_order or not isinstance(today_task, str):
            return False
        if not isinstance(expected_output, str) or not expected_output:
            return False
    elif execution_order and not isinstance(today_task, str):
        return False

    return True


@router.post("/execute")
def execute_endpoint(
    payload: ExecuteRequest
):
    if payload.autonomous:
        try:
            authorization = AutonomyPermissionService().authorize("code.execute", autonomous=True)
        except PersistenceIntegrityError:
            return build_structured_response(
                endpoint="execute",
                status="blocked",
                data={
                    "module": "execute",
                    "result": {
                        "status": "reject",
                        "blockers": ["Autonomous execution permission state is unavailable."],
                        "execution_order": [],
                        "today_task": None,
                        "task_steps": [],
                        "expected_output": "",
                    },
                    "authorization": {
                        "allowed": False,
                        "code": "autonomous_permission_state_unavailable",
                    },
                },
            )
        if not authorization["allowed"]:
            return build_structured_response(
                endpoint="execute",
                status="blocked",
                data={
                    "module": "execute",
                    "result": {
                        "status": "reject",
                        "blockers": [authorization["message"]],
                        "execution_order": [],
                        "today_task": None,
                        "task_steps": [],
                        "expected_output": "",
                    },
                    "authorization": authorization,
                },
            )

    result = execute_service.execute(
        payload.input,
        payload.builder
    )

    valid_result = validate_execute_output(result)
    if not valid_result:
        result = {
            "execution_order": [],
            "today_task": None,
            "task_steps": [],
            "expected_output": "",
            "blockers": ["Execution service returned an invalid plan."],
            "status": "refine",
        }

    response_status = "ok" if valid_result and result["status"] == "accept" else "refine"

    return build_structured_response(
        endpoint="execute",
        status=response_status,
        data={
            "module": "execute",
            "result": result
        }
    )
