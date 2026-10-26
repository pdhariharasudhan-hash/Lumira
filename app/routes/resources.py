from fastapi import APIRouter

from app.services.resources.resource_budget_service import ResourceBudgetService

router = APIRouter(prefix="/resources", tags=["Resources"])
_service = ResourceBudgetService()


@router.get("/runtime")
def get_runtime_resources():
    """Return best-effort host memory measurements and Lumira's advisory resource profile."""
    return _service.snapshot()


@router.get("/policy")
def get_resource_policy():
    """Return the current conservative execution budget for capability consumers."""
    return _service.execution_guidance()
