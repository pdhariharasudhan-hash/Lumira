from fastapi import APIRouter, HTTPException

from app.services.features.feature_activation_service import FeatureActivationService

router = APIRouter()


@router.get("/features")
def list_features():
    """Return the complete feature catalog and dependency-aware readiness."""
    return FeatureActivationService().list_features()


@router.get("/features/{feature_id}")
def get_feature(feature_id: str):
    result = FeatureActivationService().status(feature_id)
    if result.get("success") is not True:
        raise HTTPException(status_code=404, detail="Feature not found")
    return result


@router.post("/features/{feature_id}/activate")
def activate_feature(feature_id: str):
    result = FeatureActivationService().activate(feature_id)
    if result.get("success") is not True:
        if result.get("error") == "feature_not_found":
            raise HTTPException(status_code=404, detail="Feature not found")
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Feature activation was blocked",
                "feature": result.get("feature"),
                "blockers": result.get("blockers", []),
                "status": result.get("status"),
            },
        )
    return result


@router.post("/features/{feature_id}/deactivate")
def deactivate_feature(feature_id: str):
    result = FeatureActivationService().deactivate(feature_id)
    if result.get("success") is not True:
        if result.get("error") == "feature_not_found":
            raise HTTPException(status_code=404, detail="Feature not found")
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Feature deactivation was blocked",
                "feature": result.get("feature"),
                "blockers": result.get("blockers", []),
                "status": result.get("status"),
            },
        )
    return result
