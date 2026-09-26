from fastapi import APIRouter

from app.schemas.common import GenericInput
from app.services.response.response_service import build_structured_response
from app.services.brain.brain_request import BrainRequest
from app.services.brain.brain_service import BrainService

router = APIRouter()


def main_brain_flow(content: str) -> dict:
    response = BrainService().execute(
        BrainRequest(message=content.strip())
    )
    return {
        "stage": "complete" if response.success else "failed",
        "status": "ready_for_build" if response.success else "failed",
        "state": response.state.model_dump(mode="json") if response.state else None,
        "trace": response.trace,
        "error": response.error,
    }


@router.post("/brain")
def brain_endpoint(payload: GenericInput):
    content = payload.input.strip()

    if not content:
        return build_structured_response(
            endpoint="brain",
            status="error",
            data={"stage": "failed", "status": "invalid_input", "error": "input cannot be empty"},
        )

    result = main_brain_flow(content)

    return build_structured_response(
        endpoint="brain",
        status="ok" if result["stage"] == "complete" else "error",
        data=result
    )