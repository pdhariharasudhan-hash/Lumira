from fastapi import APIRouter, HTTPException, Query

from app.services.workflow_recovery.run_recovery_service import RunRecoveryService
from app.agents.workflow_engine import WorkflowEngine

router = APIRouter()


def _recovery_service_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error).strip("'"))
    if isinstance(error, ValueError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=500, detail="Workflow recovery persistence failed safely")


@router.get("/recovery/runs")
def list_recovery_runs(limit: int = Query(default=50, ge=0, le=200)):
    try:
        return {"runs": RunRecoveryService().list_runs(limit=limit)}
    except Exception as exc:
        raise _recovery_service_error(exc) from exc


@router.get("/recovery/runs/{run_id}")
def get_recovery_run(run_id: str):
    try:
        run = RunRecoveryService().get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="recovery run not found")
        return run
    except HTTPException:
        raise
    except Exception as exc:
        raise _recovery_service_error(exc) from exc


@router.post("/recovery/runs/{run_id}/window", status_code=201)
def create_recovery_window(run_id: str):
    """Create a new bounded recovery window; does not execute workflow steps."""
    try:
        return RunRecoveryService().create_recovery_window(run_id)
    except Exception as exc:
        raise _recovery_service_error(exc) from exc


@router.post("/recovery/runs/{run_id}/resume")
def resume_recovery_run(run_id: str):
    """Resume a persisted workflow only when its checkpoint passes safety checks."""
    try:
        recovery = RunRecoveryService()
        if recovery.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="recovery run not found")
        return WorkflowEngine(recovery=recovery).resume(run_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise _recovery_service_error(exc) from exc
