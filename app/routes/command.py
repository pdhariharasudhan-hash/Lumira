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
from app.services.lifecycle.project_lifecycle_service import (
    ProjectLifecycleService
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

    mode_request = None
    normalized_input = request.input.lower()
    if "enter " in normalized_input and " mode" in normalized_input:
        mode_request = CommandParserService().parse(request.input)
        if mode_request.get("capability") == "activate_mode":
            context.set_mode(mode_request["payload"]["mode"])

    brain = BrainService()

    brain_request = BrainRequest(
        message=request.input,
        project=context.get_context().get("active_project"),
        metadata={"active_mode": context.get_context().get("active_mode")},
    )

    brain_response = brain.execute(
        brain_request
    )

    if not brain_response.success:
        return {
            "success": False,
            "brain": {
                "state": brain_response.state.model_dump(mode="json") if brain_response.state else None,
                "trace": brain_response.trace,
                "error": brain_response.error,
            },
            "context": context.get_context(),
        }

    intent = IntentClassifierService().classify(request.input)
    if intent in {"search", "chat"}:
        context.clear_project()

    parsed = CommandParserService().parse(request.input)
    if not parsed["success"]:
        if request.input.strip().lower().startswith("add ") and context.get_context().get("active_project"):
            parsed = {
                "success": True,
                "capability": "continue_project",
                "payload": {"instruction": request.input},
            }
        else:
            return {
                "success": False,
                "intent": intent,
                "parsed": parsed,
                "brain": {
                    "state": brain_response.state.model_dump(mode="json"),
                    "trace": brain_response.trace,
                },
                "context": context.get_context(),
            }

    mode_state = brain_response.state.mode

    capability = parsed["capability"]

    if capability == "activate_mode":
        result = {
            "success": True,
            "capability": capability,
            "mode": mode_state.active_mode,
        }
    elif capability == "continue_project":
        active_project = context.get_context().get("active_project")
        active_version = context.get_context().get("active_version")
        existing = ProjectLifecycleService().get_project_version(
            active_project,
            active_version,
        ) if active_project and active_version else {"success": False}
        if not existing["success"]:
            result = {"success": False, "error": "No active project version to continue"}
        else:
            result = ProjectLifecycleService().continue_project(
                metadata=existing["data"]["metadata"],
                instruction=parsed["payload"]["instruction"],
            )
            if result.get("success"):
                context.set_version(result["saved_to"].replace("\\", "/").rsplit("/", 1)[-1])
    else:
        result = CapabilityRouterService().execute(
            capability,
            parsed["payload"],
            mode_state=mode_state,
        )

    if isinstance(result, dict) and result.get("success") and result.get("project_name"):
        context.set_project(result["project_name"])
        context.set_version(result.get("metadata", {}).get("version", "v1"))

    return {

        "success": result.get("success", True) if isinstance(result, dict) else True,

        "intent":
        intent,

        "parsed":
        parsed,

        "brain": {
            "state": brain_response.state.model_dump(mode="json"),
            "trace": brain_response.trace,
        },

        "result":
        result,

        "context":
        context.get_context()
    }