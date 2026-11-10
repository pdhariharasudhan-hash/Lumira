from fastapi import APIRouter

from app.services.capabilities.phase_zero_capability_service import PhaseZeroCapabilityService

router = APIRouter()


@router.get("/capabilities/phase-zero")
def phase_zero_capabilities():
    service = PhaseZeroCapabilityService()
    return {"success": True, "summary": service.summary(), "capabilities": service.inventory()}
