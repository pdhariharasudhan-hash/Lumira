"""Brain preflight and durable authorization for workflow execution."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.core.lumira_core import LumiraCore
from app.services.autonomy.autonomy_permission_service import AutonomyPermissionService
from app.services.security.security_audit_log_service import SecurityAuditLogService


logger = logging.getLogger(__name__)


def preflight_workflow_execution(
    goal: str,
    *,
    session_id: str | None = None,
    project_id: str | None = None,
    workspace: str = "default",
    source: str = "workflow_run",
    run_id: str | None = None,
    autonomous: bool = False,
    core_factory=None,
    autonomy_permissions: Any | None = None,
    audit_log: Any | None = None,
) -> dict:
    """Require durable authorization, a Brain verification and audit evidence.

    Autonomous workflow dispatch is blocked unless the owner has explicitly
    enabled the workflow.run permission. Audit persistence is a prerequisite
    for crossing the workflow execution boundary.
    """
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 10_000:
        return {
            "allowed": False,
            "state": "rejected",
            "code": "invalid_workflow_goal",
            "message": "Workflow goal must contain 1-10000 characters.",
        }
    if not isinstance(autonomous, bool):
        return {
            "allowed": False,
            "state": "rejected",
            "code": "invalid_autonomy_mode",
            "message": "Workflow autonomy mode must be an explicit boolean.",
        }
    if session_id is not None and (
        not isinstance(session_id, str) or len(session_id) > 256
    ):
        return {"allowed": False, "state": "rejected", "code": "invalid_session"}
    if project_id is not None and (
        not isinstance(project_id, str) or len(project_id) > 256
    ):
        return {"allowed": False, "state": "rejected", "code": "invalid_project"}

    session = session_id or ""
    goal_fingerprint = hashlib.sha256(goal.strip().encode("utf-8")).hexdigest()
    actor = "session:" + hashlib.sha256(session.encode("utf-8")).hexdigest()[:16]
    permissions = autonomy_permissions or AutonomyPermissionService()
    audit = audit_log or SecurityAuditLogService()

    if autonomous:
        try:
            authorization = permissions.authorize("workflow.run", autonomous=True)
        except Exception:
            return {
                "allowed": False,
                "state": "blocked",
                "code": "autonomous_permission_state_unavailable",
                "message": "Workflow execution is blocked because permission state is unavailable.",
            }
        if authorization.get("allowed") is not True:
            return {
                "allowed": False,
                "state": "blocked",
                "code": authorization.get("code", "autonomous_permission_required"),
                "message": authorization.get(
                    "message",
                    "Explicit owner permission is required for autonomous workflow execution.",
                ),
            }

    audit_details = {
        "goal_sha256": goal_fingerprint,
        "source": source[:80] if isinstance(source, str) else "workflow_run",
        "run_id": run_id[:128] if isinstance(run_id, str) else None,
        "autonomous": autonomous,
    }
    try:
        audit.append(
            event_type="workflow_execution",
            action="workflow.preflight",
            outcome="started",
            actor=actor,
            details=audit_details,
        )
    except Exception:
        return {
            "allowed": False,
            "state": "blocked",
            "code": "security_audit_unavailable",
            "message": "Workflow execution is blocked because its security audit event could not be persisted.",
        }

    metadata = {"source": source}
    if isinstance(run_id, str) and run_id:
        metadata["workflow_run_id"] = run_id

    try:
        core = (core_factory or LumiraCore)()
        brain = core.understand(
            goal,
            session_id=session,
            project=project_id or "",
            workspace=workspace or "default",
            metadata=metadata,
        )
    except Exception as exc:
        logger.error("Workflow Brain preflight failed (%s)", type(exc).__name__)
        result = {
            "allowed": False,
            "state": "failed",
            "code": "brain_preflight_failed",
            "message": "Lumira Brain could not verify this request for workflow execution.",
        }
        _record_outcome(audit, actor, audit_details, "failed", result["code"])
        return result

    brain_state = brain.get("state") if isinstance(brain, dict) else None
    verification = (
        brain_state.get("verification_result")
        if isinstance(brain_state, dict)
        else None
    )
    if (
        not isinstance(brain, dict)
        or brain.get("success") is not True
        or not isinstance(verification, dict)
        or verification.get("ready_for_execution") is not True
    ):
        rejected = isinstance(brain, dict) and brain.get("success") is True
        result = {
            "allowed": False,
            "state": "rejected" if rejected else "failed",
            "code": "brain_verification_rejected" if rejected else "brain_preflight_failed",
            "message": (
                "Lumira Brain did not verify this request for workflow execution."
                if rejected
                else "Lumira Brain could not verify this request for workflow execution."
            ),
        }
        _record_outcome(audit, actor, audit_details, result["state"], result["code"])
        return result

    result = {
        "allowed": True,
        "state": "authorized",
        "code": "workflow_preflight_passed",
        "brain_execution_id": (
            brain_state.get("execution_context", {}).get("execution_id")
            if isinstance(brain_state.get("execution_context"), dict)
            else None
        ),
    }
    if not _record_outcome(audit, actor, audit_details, "authorized", result["code"]):
        return {
            "allowed": False,
            "state": "blocked",
            "code": "workflow_audit_completion_failed",
            "message": "Brain verification passed, but workflow execution remains blocked because its final audit event could not be persisted.",
        }
    return result


def _record_outcome(
    audit: Any,
    actor: str,
    details: dict,
    outcome: str,
    code: str,
) -> bool:
    try:
        audit.append(
            event_type="workflow_execution",
            action="workflow.preflight",
            outcome=outcome,
            actor=actor,
            details={**details, "result_code": code},
        )
        return True
    except Exception:
        logger.error("Workflow preflight outcome audit persistence failed")
        return False
