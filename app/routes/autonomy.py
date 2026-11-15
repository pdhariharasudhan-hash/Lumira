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
        result = service.set_permission(operation, request.enabled, request.reason)
        if result.get("success") is not True:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": result.get("code", "permission_update_audit_failed"),
                    "side_effect_may_have_occurred": result.get("side_effect_may_have_occurred", False),
                },
            )
        return result
    except (ValueError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
