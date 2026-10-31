from fastapi import APIRouter, HTTPException

from app.services.system.core_feature_bridge_service import CoreFeatureBridgeService

router = APIRouter(prefix="/core", tags=["Core Bridge"])


@router.get("/features")
def core_feature_overview():
    try:
        return CoreFeatureBridgeService().overview()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Core feature bridge is unavailable") from exc


@router.get("/features/{feature_id}/readiness")
def core_feature_readiness(feature_id: str):
    result = CoreFeatureBridgeService().readiness(feature_id)
    if result.get("success") is not True:
        raise HTTPException(status_code=404, detail="Feature not found")
    return result
