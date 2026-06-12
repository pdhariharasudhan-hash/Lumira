from typing import Dict, Any

from fastapi import APIRouter
from app.schemas.common import GenericInput

from app.services.builder_service import (
    BuilderService
)

from app.services.response_service import (
    build_structured_response
)

router = APIRouter()

builder_service = BuilderService()


def validate_builder_output(
    result: Dict[str, Any]
) -> bool:

    required_fields = [
        "objective",
        "scope",
        "suggested_steps",
        "priority",
        "status"
    ]

    for field in required_fields:

        if field not in result:
            return False

    if not isinstance(
        result["suggested_steps"],
        list
    ):
        return False

    if len(
        result["suggested_steps"]
    ) == 0:
        return False

    return True


@router.post("/builder")
def builder_endpoint(
    payload: GenericInput
):

    content = payload.input.strip()

    result = builder_service.build(
        content
    )

    if not validate_builder_output(
        result
    ):

        result = {
            "objective": "fallback build plan",
            "scope": "small",
            "suggested_steps": [
                {
                    "id": "step_1",
                    "action": "create fallback script",
                    "inputs": {},
                    "expected_output": "fallback created",
                    "dependencies": []
                }
            ],
            "priority": "medium",
            "status": "fallback"
        }

    return build_structured_response(
        endpoint="builder",
        status="ok",
        data={
            "module": "builder",
            "result": result
        }
    )








    