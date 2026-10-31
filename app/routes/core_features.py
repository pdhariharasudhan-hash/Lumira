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


@router.get("/features/{feature_id}/plan")
def core_feature_plan(feature_id: str):
    result = CoreFeatureBridgeService().features.dependency_plan(feature_id)
    if result.get("success") is not True:
        raise HTTPException(status_code=404, detail="Feature not found")
    return result


@router.post("/features/{feature_id}/activate")
def core_feature_activate(feature_id: str):
    bridge = CoreFeatureBridgeService()
    plan = bridge.features.dependency_plan(feature_id)
    if plan.get("success") is not True:
        raise HTTPException(status_code=404, detail="Feature not found")
    if plan.get("ready") is not True:
        raise HTTPException(status_code=409, detail=plan)
    return bridge.features.activate_with_dependencies(feature_id)
