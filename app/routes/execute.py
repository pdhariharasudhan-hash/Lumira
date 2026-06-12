from typing import Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.execute_service import ExecuteService
from app.services.response_service import (
    build_structured_response
)

router = APIRouter()

execute_service = ExecuteService()


class ExecuteRequest(BaseModel):
    input: str
    builder: Dict[str, Any]


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

    if len(execution_order) == 0:
        return False

    if not isinstance(
        today_task,
        str
    ):
        return False

    if not isinstance(
        task_steps,
        list
    ):
        return False

    if not isinstance(
        expected_output,
        str
    ):
        return False

    if not isinstance(
        blockers,
        list
    ):
        return False

    if status not in [
        "accept",
        "refine",
        "reject"
    ]:
        return False

    return True


@router.post("/execute")
def execute_endpoint(
    payload: ExecuteRequest
):

    result = execute_service.execute(
        payload.input,
        payload.builder
    )

    if not validate_execute_output(
        result
    ):
        result["status"] = "refine"

    return build_structured_response(
        endpoint="execute",
        status="ok",
        data={
            "module": "execute",
            "result": result
        }
    )