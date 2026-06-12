from fastapi import APIRouter

from app.schemas.common import (
    GenericInput
)

from app.services.command_parser_service import (
    CommandParserService
)

from app.services.capability_router_service import (
    CapabilityRouterService
)

from app.services.execution_context_service import (
    ExecutionContextService
)

from app.services.intent_classifier_service import (
    IntentClassifierService
)

router = APIRouter()


@router.post(
    "/command"
)
def command(
    request: GenericInput
):

    context = (
        ExecutionContextService()
    )

    context.set_goal(
        request.input
    )

    context.set_pipeline_stage(
        "command"
    )

    context.set_last_command(
        request.input
    )

    intent = (
        IntentClassifierService()
        .classify(
            request.input
        )
    )

    if intent in [
        "search",
        "chat"
    ]:

        context.clear_project()

    parsed = (
        CommandParserService()
        .parse(
            request.input
        )
    )

    if not parsed[
        "success"
    ]:

        return {

            "success":
            False,

            "parsed":
            parsed,

            "context":
            context.get_context()
        }

    result = (
        CapabilityRouterService()
        .execute(
            parsed[
                "capability"
            ],

            parsed[
                "payload"
            ]
        )
    )

    return {

        "success":
        True,

        "intent":
        intent,

        "parsed":
        parsed,

        "result":
        result,

        "context":
        context.get_context()
    }