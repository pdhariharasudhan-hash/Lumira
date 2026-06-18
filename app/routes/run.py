from fastapi import APIRouter

from app.schemas.common import (
    GenericInput
)

from app.agents.workflow_engine import (
    WorkflowEngine
)

router = APIRouter()


@router.post(
    "/run"
)
def run_pipeline(
    request: GenericInput
):

    result = (

        WorkflowEngine()
        .execute(

            request.input
        )
    )

    return {

        "success":
        result[
            "success"
        ],

        "endpoint":
        "run",

        "status":
        "ok",

        "data":
        result
    }