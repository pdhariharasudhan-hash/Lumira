from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services.security.security_audit_log_service import SecurityAuditLogService
from app.services.security.unsafe_operation_detection_service import UnsafeOperationDetectionService

router = APIRouter(prefix="/security", tags=["security"])


class SecurityPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction: str = Field(min_length=1, max_length=10_000)


@router.post("/preflight")
def security_preflight(request: SecurityPreflightRequest):
    result = UnsafeOperationDetectionService.analyze(request.instruction)
    try:
        SecurityAuditLogService().append(
            event_type="instruction_preflight",
            action="security_preflight",
            outcome="allowed" if result.get("allowed") is True else "blocked",
            actor="api",
            details={
                "finding_rules": [item.get("rule") for item in result.get("findings", [])],
                "finding_count": len(result.get("findings", [])),
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Security audit is unavailable; the preflight result cannot be trusted.",
        ) from exc
    return result


@router.get("/audit/integrity")
def security_audit_integrity():
    result = SecurityAuditLogService().verify_integrity()
    if result.get("valid") is not True:
        raise HTTPException(status_code=503, detail="Security audit integrity check failed.")
    return result


@router.get("/audit/events")
def security_audit_events(limit: int = Query(default=50, ge=1, le=100)):
    try:
        events = SecurityAuditLogService().recent_events(limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Security audit events are unavailable.") from exc
    return {"events": events, "count": len(events)}
