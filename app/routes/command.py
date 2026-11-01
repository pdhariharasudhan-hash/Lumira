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
from app.services.brain.brain_agent_orchestrator import BrainAgentOrchestrator


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
from app.services.brain.public_brain_view import public_brain_state, public_brain_trace
from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
from app.services.sessions.session_manager_service import redact_sensitive_text

router = APIRouter()


def _command_result_success(result) -> bool:
    """Reject explicit failure states while preserving legacy success defaults."""
    if not isinstance(result, dict):
        return False
    # Explicit failure and non-terminal states win over a contradictory success flag.
    non_success_states = {
        "failed", "failure", "rejected", "blocked", "cancelled", "canceled", "error",
        "pending", "running", "in_progress", "in-progress", "queued", "started", "working",
    }
    for key in ("status", "state"):
        value = result.get(key)
        if key in result and (not isinstance(value, str) or not value.strip()):
            return False
        if isinstance(value, str) and value.strip().lower() in non_success_states:
            return False
    if "success" in result:
        return result["success"] is True
    # Older capabilities that omit success retain their legacy default otherwise.
    return True


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

    parsed = CommandParserService().parse(request.input)
    agent_orchestrator = None
    if parsed.get("success") and parsed.get("capability") == "agent_task":
        payload = parsed.get("payload", {})
        agent_orchestrator = BrainAgentOrchestrator()
        preflight = agent_orchestrator.validate_request(
            payload.get("task"),
            agent_name=payload.get("agent_name"),
        )
        if preflight:
            return {
                "success": False,
                "intent": IntentClassifierService().classify(request.input),
                "parsed": parsed,
                "result": preflight,
                "context": session,
                "session_id": session["session_id"],
            }

    brain = BrainService()
    try:
        shared_core_context = CoreRuntimeBridgeService().context(
            session_id=session["session_id"],
            project_id=session.get("active_project"),
            goal_id=session.get("goal_id"),
        ).get("context", {})
    except Exception:
        shared_core_context = {}

    brain_request = BrainRequest(
        message=request.input,
        project=session.get("active_project"),
        session_id=session["session_id"],
        workspace=request.workspace_id,
        metadata={
            "core_context": shared_core_context,
            "active_mode": (
                parsed["payload"]["mode"]
                if parsed.get("success") and parsed.get("capability") == "activate_mode"
                else session.get("active_mode")
            )
        },
    )

    brain_response = brain.execute(
        brain_request
    )

    # Only a literal boolean success may authorize capability execution.
    if brain_response.success is not True:
        return {
            "success": False,
            "brain": {
                "state": public_brain_state(brain_response.state),
                "trace": public_brain_trace(brain_response.trace),
                "error": redact_sensitive_text(brain_response.error) if brain_response.error else None,
            },
            "context": session,
            "session_id": session["session_id"],
        }

    session = sessions.get_session(session["session_id"])

    intent = IntentClassifierService().classify(request.input)
    if not parsed["success"]:
        try:
            from app.agents.agent_manager import AgentManager
            agent_recommendation = AgentManager().select_agent(request.input)
        except Exception:
            agent_recommendation = {"success": False, "selected_agent": None, "reason": "recommendation_unavailable"}
        sessions.append_message(session["session_id"], "assistant", "I could not map that request to a supported capability.")
        return {
            "success": False,
            "intent": intent,
            "parsed": parsed,
            "agent_recommendation": agent_recommendation,
            "brain": {
                "state": public_brain_state(brain_response.state),
                "trace": public_brain_trace(brain_response.trace),
            },
            "context": session,
            "session_id": session["session_id"],
        }

    mode_state = brain_response.state.mode

    capability = parsed["capability"]
    if capability == "activate_mode":
        # Commit the mode change only after the brain has passed its success gate.
        session = sessions.update_context(
            session["session_id"],
            active_mode=parsed["payload"]["mode"],
        )

    if capability == "agent_task":
        orchestrator = agent_orchestrator or BrainAgentOrchestrator()
        result = orchestrator.execute_after_brain(
            parsed["payload"]["task"],
            brain_response,
            agent_name=parsed["payload"].get("agent_name"),
        )
    elif capability == "activate_mode":
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
            {
                **parsed["payload"],
                "session_id": session["session_id"],
                "project_id": session.get("active_project"),
                "goal_id": session.get("goal_id"),
            },
            mode_state=mode_state,
        )

    if _command_result_success(result) and result.get("goal_id"):
        session = sessions.update_context(
            session["session_id"],
            goal_id=result["goal_id"],
            current_goal=(result.get("goal") or {}).get("title") or session.get("current_goal"),
        )
    if _command_result_success(result):
        workflow = result.get("workflow")
        artifact = result.get("artifact")
        if isinstance(workflow, dict) and workflow.get("workflow_id"):
            sessions.link_record(session["session_id"], "workflow", workflow["workflow_id"])
        if isinstance(artifact, dict) and artifact.get("artifact_id"):
            sessions.link_record(session["session_id"], "artifact", artifact["artifact_id"])

    if _command_result_success(result) and result.get("project_name"):
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
            and _command_result_success(result)
            and result.get("success") is True
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
    elif _command_result_success(result) and capability == "remember_decision":
        sessions.link_record(session["session_id"], "memory", result["decision"]["decision_id"])

    session = sessions.get_session(session["session_id"])
    sessions.snapshot_context(session["session_id"])
    sessions.append_message(
        session["session_id"],
        "assistant",
        (
            f"{capability} plan created."
            if _command_result_success(result) and result.get("status") == "planned"
            else f"{capability} {'completed' if _command_result_success(result) else 'did not complete'}."
        ),
        metadata={"capability": capability, "success": _command_result_success(result)},
    )

    context = {
        "current_goal": session.get("current_goal"),
        "goal_id": session.get("goal_id"),
        "active_project": session.get("active_project"),
        "active_version": session.get("active_version"),
        "current_stage": capability,
        "last_command": session.get("last_command"),
        "active_mode": session.get("active_mode"),
        "recent_artifact_ids": session.get("recent_artifact_ids", []),
        "recent_workflow_ids": session.get("recent_workflow_ids", []),
    }

    return {

        "success": _command_result_success(result),

        "session_id": session["session_id"],

        "intent":
        intent,

        "parsed":
        parsed,

        "brain": {
            "state": public_brain_state(brain_response.state),
            "trace": public_brain_trace(brain_response.trace),
        },

        "result":
        result,

        "context":
        context
    }
