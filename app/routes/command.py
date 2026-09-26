from fastapi import APIRouter

from app.schemas.common import (
    GenericInput
)

from app.services.command_parser_service import (
    CommandParserService
)

from app.services.brain.brain_request import (
    BrainRequest
)

from app.services.brain.brain_service import (
    BrainService
)


from app.services.capabilities.capability_router_service import (
    CapabilityRouterService
)

from app.services.execution.execution_context_service import (
    ExecutionContextService
)

from app.services.language.intent_classifier_service import (
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

    context.set_stage(
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

    brain = BrainService()

    brain_request = BrainRequest(
        message=request.input
    )

    brain_state = brain.create_state(
        brain_request
    )

    brain._resolve_mode(
        brain_state
    )

    mode_state = brain_state.mode

    result = (
        CapabilityRouterService()
        .execute(
            parsed[
                "capability"
            ],

            parsed[
                "payload"
            ]
        ,
            mode_state=mode_state)
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