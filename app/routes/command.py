from fastapi import APIRouter, HTTPException

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

from app.services.language.intent_classifier_service import (
    IntentClassifierService
)
from app.services.lifecycle.project_lifecycle_service import (
    ProjectLifecycleService
)
from app.services.sessions.session_manager_service import SessionManagerService
from app.services.sessions.reference_resolution_service import ReferenceResolutionService
from app.services.memory.memory_service import MemoryService, MemoryValidationError

router = APIRouter()


@router.post(
    "/command"
)
def command(
    request: GenericInput
):
    sessions = SessionManagerService()
    try:
        session = sessions.resolve_session(
            request.session_id,
            workspace_id=request.workspace_id,
            project_id=request.project_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    mode_request = None
    normalized_input = request.input.lower()
    if "enter " in normalized_input and " mode" in normalized_input:
        mode_request = CommandParserService().parse(request.input)
        if mode_request.get("capability") == "activate_mode":
            session = sessions.update_context(
                session["session_id"],
                active_mode=mode_request["payload"]["mode"],
            )

    reference = ReferenceResolutionService().resolve(request.input, session)
    if reference["status"] in {"unresolved", "ambiguous"}:
        sessions.append_message(session["session_id"], "user", request.input)
        message = (
            "Which project do you mean?"
            if reference["status"] == "ambiguous"
            else "I do not have an active project to resolve that reference."
        )
        sessions.append_message(
            session["session_id"],
            "assistant",
            message,
            metadata={"reference_resolution": reference["status"]},
        )
        return {
            "success": False,
            "session_id": session["session_id"],
            "clarification_required": True,
            "message": message,
            "reference_resolution": reference,
        }

    if reference["status"] == "resolved" and not session.get("active_project"):
        session = sessions.update_context(
            session["session_id"],
            active_project=reference["project_id"],
        )

    brain = BrainService()

    brain_request = BrainRequest(
        message=request.input,
        project=session.get("active_project"),
        session_id=session["session_id"],
        workspace=request.workspace_id,
        metadata={"active_mode": session.get("active_mode")},
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
            "context": session,
            "session_id": session["session_id"],
        }

    intent = IntentClassifierService().classify(request.input)
    parsed = CommandParserService().parse(request.input)
    if not parsed["success"]:
        sessions.append_message(session["session_id"], "assistant", "I could not map that request to a supported capability.")
        return {
            "success": False,
            "intent": intent,
            "parsed": parsed,
            "brain": {
                "state": brain_response.state.model_dump(mode="json"),
                "trace": brain_response.trace,
            },
            "context": session,
            "session_id": session["session_id"],
        }

    mode_state = brain_response.state.mode

    capability = parsed["capability"]

    if capability == "activate_mode":
        result = {
            "success": True,
            "capability": capability,
            "mode": mode_state.active_mode,
        }
    elif capability == "resume_project":
        project = session.get("active_project")
        version = session.get("active_version")
        if not project or not version:
            result = {"success": False, "error": "No active project is available in this session"}
        else:
            result = ProjectLifecycleService().get_project_version(project, version)
            result = {
                "success": result.get("success", False),
                "capability": capability,
                "project_name": project,
                "version": version,
                "project": result.get("data"),
            }
    elif request.input.strip().lower().startswith("remember "):
        memory = MemoryService()
        decision_text = request.input.strip()[len("remember "):].strip()
        try:
            decision = memory.record_decision(
                decision=decision_text,
                reason="Explicit user instruction.",
                session_id=session["session_id"],
                project_id=session["active_project"],
                goal_id=session.get("goal_id"),
                confidence=1.0,
            )
            sessions.link_record(session["session_id"], "decision", decision["decision_id"])
            result = {"success": True, "capability": "remember_decision", "decision": decision}
        except MemoryValidationError as exc:
            result = {"success": False, "error": "Durable memory is unavailable or incompatible"}
    elif capability == "continue_project":
        active_project = session.get("active_project")
        active_version = session.get("active_version")
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
                session = sessions.update_context(
                    session["session_id"],
                    active_version=result["saved_to"].replace("\\", "/").rsplit("/", 1)[-1],
                )
    else:
        result = CapabilityRouterService().execute(
            capability,
            parsed["payload"],
            mode_state=mode_state,
        )

    if isinstance(result, dict) and result.get("success") and result.get("project_name"):
        session = sessions.update_context(
            session["session_id"],
            active_project=result["project_name"],
            active_version=result.get("metadata", {}).get("version", "v1"),
        )
        if session.get("goal_id"):
            MemoryService().update_goal(
                session["goal_id"],
                project_id=result["project_name"],
            )

    if capability in {"project_generation", "continue_project"}:
        memory = MemoryService()
        validation = result.get("validation", {}) if isinstance(result, dict) else {}
        verified_project = bool(
            isinstance(result, dict)
            and result.get("success")
            and (capability != "project_generation" or validation.get("valid") is True)
        )
        experience = memory.record_experience(
            "success" if verified_project else "failure",
            summary=f"{capability}: {request.input}",
            outcome="Generated project version validated and saved." if verified_project else "Project operation did not complete successfully.",
            project_id=session.get("active_project"),
            goal_id=session.get("goal_id"),
            lessons=["Validate generated source before saving a new project version."] if capability == "project_generation" and verified_project else [],
            source_run=brain_response.state.execution_context.execution_id,
            verified=verified_project,
        )
        sessions.link_record(session["session_id"], "experience", experience["experience_id"])
        learning = memory.consolidate_learning(experience) if verified_project else None
        if learning:
            sessions.link_record(session["session_id"], "memory", learning["learning_id"])
            from app.services.history.event_logger_service import EventLoggerService
            EventLoggerService().log(
                event="learning_created",
                source="command",
                data={"session_id": session["session_id"], "learning_id": learning["learning_id"]},
            )
    elif isinstance(result, dict) and result.get("success") and capability == "remember_decision":
        sessions.link_record(session["session_id"], "memory", result["decision"]["decision_id"])

    session = sessions.get_session(session["session_id"])
    sessions.snapshot_context(session["session_id"])
    sessions.append_message(
        session["session_id"],
        "assistant",
        f"{capability} {'completed' if isinstance(result, dict) and result.get('success') else 'did not complete'}.",
        metadata={"capability": capability, "success": bool(isinstance(result, dict) and result.get("success"))},
    )

    context = {
        "current_goal": session.get("current_goal"),
        "active_project": session.get("active_project"),
        "active_version": session.get("active_version"),
        "current_stage": capability,
        "last_command": session.get("last_command"),
        "active_mode": session.get("active_mode"),
    }

    return {

        "success": result.get("success", True) if isinstance(result, dict) else True,

        "session_id": session["session_id"],

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
        context
    }