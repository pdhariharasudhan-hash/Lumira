"""Dependency-aware feature lifecycle API with durable security audit records."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.features.feature_activation_service import FeatureActivationService
from app.services.security.security_audit_log_service import SecurityAuditLogService

router = APIRouter()


def _audit(action: str, outcome: str, feature_id: str, details: dict | None = None) -> None:
    SecurityAuditLogService().append(
        event_type="feature_lifecycle",
        action=action,
        outcome=outcome,
        actor="local_owner",
        details={"feature_id": feature_id, **(details or {})},
    )


def _audit_preflight(action: str, feature_id: str) -> None:
    try:
        _audit(action, "requested", feature_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Feature state was not changed because the security audit log is unavailable.") from exc


def _audit_completion(action: str, feature_id: str, result: dict) -> None:
    try:
        _audit(action, "completed", feature_id, {
            "activation_order": result.get("activation_order"),
            "activated": result.get("activated"),
            "status": result.get("status"),
        })
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "feature_lifecycle_audit_failed",
                "feature_id": feature_id,
                "side_effect_may_have_occurred": True,
            },
        ) from exc


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


@router.get("/features/{feature_id}/bridge-plan")
def feature_bridge_plan(feature_id: str):
    result = FeatureActivationService().dependency_plan(feature_id)
    if result.get("success") is not True:
        raise HTTPException(status_code=404, detail="Feature not found")
    return result


@router.post("/features/{feature_id}/activate-bridge")
def activate_feature_bridge(feature_id: str):
    """Activate the requested feature through its full dependency bridge."""
    _audit_preflight("feature.activate_bridge", feature_id)
    result = FeatureActivationService().activate_with_dependencies(feature_id)
    if result.get("success") is not True:
        if result.get("error") == "feature_not_found":
            raise HTTPException(status_code=404, detail="Feature not found")
        try:
            _audit("feature.activate_bridge", "blocked", feature_id, {"blockers": result.get("blockers", [])})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Feature activation was blocked and the audit outcome could not be recorded.") from exc
        raise HTTPException(status_code=409, detail=result)
    _audit_completion("feature.activate_bridge", feature_id, result)
    return result


@router.post("/features/{feature_id}/activate")
def activate_feature(feature_id: str):
    _audit_preflight("feature.activate", feature_id)
    result = FeatureActivationService().activate(feature_id)
    if result.get("success") is not True:
        if result.get("error") == "feature_not_found":
            raise HTTPException(status_code=404, detail="Feature not found")
        try:
            _audit("feature.activate", "blocked", feature_id, {"blockers": result.get("blockers", [])})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Feature activation was blocked and the audit outcome could not be recorded.") from exc
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Feature activation was blocked",
                "feature": result.get("feature"),
                "blockers": result.get("blockers", []),
                "status": result.get("status"),
            },
        )
    _audit_completion("feature.activate", feature_id, result)
    return result


@router.post("/features/{feature_id}/deactivate")
def deactivate_feature(feature_id: str):
    _audit_preflight("feature.deactivate", feature_id)
    result = FeatureActivationService().deactivate(feature_id)
    if result.get("success") is not True:
        if result.get("error") == "feature_not_found":
            raise HTTPException(status_code=404, detail="Feature not found")
        try:
            _audit("feature.deactivate", "blocked", feature_id, {"blockers": result.get("blockers", [])})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Feature deactivation was blocked and the audit outcome could not be recorded.") from exc
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Feature deactivation was blocked",
                "feature": result.get("feature"),
                "blockers": result.get("blockers", []),
                "status": result.get("status"),
            },
        )
    _audit_completion("feature.deactivate", feature_id, result)
    return result
