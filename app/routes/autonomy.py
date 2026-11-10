from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.services.autonomy.autonomy_permission_service import (
    AUTONOMY_OPERATIONS,
    AutonomyPermissionService,
)
from app.services.persistence.atomic_json_store import PersistenceIntegrityError

router = APIRouter(prefix="/autonomy", tags=["Autonomy"])
service = AutonomyPermissionService()


class PermissionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
    reason: str | None = Field(default=None, max_length=500)


@router.get("/permissions")
def autonomy_permissions():
    try:
        return service.status()
    except PersistenceIntegrityError as exc:
        raise HTTPException(status_code=503, detail="Autonomy permission state is unavailable") from exc


@router.put("/permissions/{operation:path}")
def update_autonomy_permission(operation: str, request: PermissionUpdate):
    if operation not in AUTONOMY_OPERATIONS:
        raise HTTPException(status_code=404, detail="unsupported autonomous operation")
    try:
        return service.set_permission(operation, request.enabled, request.reason)
    except (ValueError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
