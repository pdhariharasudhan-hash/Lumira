from fastapi import APIRouter, HTTPException, Query

from app.core.lumira_core import LumiraCore
from app.services.brain.workflow_execution_gate import preflight_workflow_execution
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
    approval = preflight_workflow_execution(
        request.input,
        session_id=request.session_id,
        project_id=request.project_id,
        workspace=request.workspace_id,
        source="workflow_run",
        core_factory=LumiraCore,
    )
    if approval.get("allowed") is not True:
        return {
            "success": False,
            "endpoint": "run",
            "status": approval["state"],
            "data": {key: value for key, value in approval.items() if key != "allowed"},
        }

    result = (

        WorkflowEngine()
        .execute(
            request.input,
            session_id=request.session_id,
            project_id=request.project_id,
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
        "ok" if result.get("success") else result.get("state", "failed"),

        "data":
        result
    }


@router.get("/runs")
def list_runs(limit: int = Query(default=50, ge=0, le=200)):
    from app.services.workflow_recovery.run_recovery_service import RunRecoveryService

    return {"runs": RunRecoveryService().list_runs(limit)}


@router.get("/runs/{run_id}")
def inspect_run(run_id: str):
    result = WorkflowEngine().inspect(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="run not found")
    return result


@router.post("/runs/{run_id}/resume")
def resume_run(run_id: str):
    result = WorkflowEngine().resume(
        run_id,
        before_resume=lambda run: preflight_workflow_execution(
            run.get("goal", ""),
            session_id=run.get("session_id"),
            project_id=(run.get("core_context") or {}).get("project_id")
            if isinstance(run.get("core_context"), dict)
            else None,
            source="workflow_resume",
            run_id=run_id,
            core_factory=LumiraCore,
        ),
    )
    if result.get("code") == "run_not_found":
        raise HTTPException(status_code=404, detail="run not found")
    if result.get("code") == "session_closed":
        raise HTTPException(status_code=409, detail="closed sessions cannot resume workflow runs")
    if result.get("code") in {"manual_reconciliation_required", "resume_limit_reached", "run_already_completed"}:
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    if not WorkflowEngine.cancel(run_id):
        raise HTTPException(status_code=409, detail="run has no active capability process")
    return {"success": True, "run_id": run_id, "status": "cancellation_requested"}
