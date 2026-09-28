from typing import Dict, Any

from fastapi import APIRouter
from app.schemas.common import GenericInput

from app.services.builder.builder_service import (
    BuilderService
)

from app.services.response.response_service import (
    build_structured_response
)

router = APIRouter()

builder_service = BuilderService()


def analyze_build_request(content: str) -> Dict[str, Any]:
    text = (content or "").strip()

    if not text:
        return {
            "objective": "",
            "scope": "small",
            "suggested_steps": [],
            "priority": "medium",
            "status": "refine",
            "reason": "empty input"
        }

    result = builder_service.build(text)

    if not validate_builder_output(result):
        return {
            "objective": text,
            "scope": "small",
            "suggested_steps": [],
            "priority": "medium",
            "status": "refine",
            "reasons": ["The request does not form a valid implementation plan."],
        }

    return result


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

    status = result.get("status")
    if status not in {"accept", "refine"}:
        return False
    if status == "accept" and not result["suggested_steps"]:
        return False
    if len(result["suggested_steps"]) > BuilderService.MAX_PLAN_STEPS:
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

    if not validate_builder_output(result):
        return build_structured_response(
            endpoint="builder",
            status="error",
            data={"module": "builder", "result": {"status": "reject", "error": "builder returned an invalid plan"}},
        )

    return build_structured_response(
        endpoint="builder",
        status="ok" if result["status"] == "accept" else "refine",
        data={
            "module": "builder",
            "result": result
        }
    )









