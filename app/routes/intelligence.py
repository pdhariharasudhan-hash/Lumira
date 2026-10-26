from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.brain.brain_service import BrainService
from app.services.features.feature_activation_service import FeatureActivationService
from app.services.history.pipeline_history_service import PipelineHistoryService
from app.services.language.intent_classifier_service import IntentClassifierService
from app.services.language.language_detection_service import LanguageDetectionService
from app.services.modes.mode_detection_service import ModeDetectionService
from app.services.modes.mode_registry_service import ModeRegistryService
from app.services.providers.provider_registry import ProviderRegistry, PROVIDER_STATUS_NAMES
from app.services.sessions.session_manager_service import SessionManagerService

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class SelectModeRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    mode_id: str = Field(min_length=1, max_length=50)


@router.get("/intelligence/status")
def intelligence_status():
    """Expose the existing brain pipeline and capability readiness in one place."""
    brain = BrainService()
    feature_summary = FeatureActivationService().list_features()
    return {
        "success": True,
        "brain": {
            "modules": [module.__class__.__name__ for module in brain.get_modules()],
            "execution_order": brain.get_execution_order(),
            "stages": brain.get_stage_names(),
            "total_stages": brain.total_stages(),
        },
        "features": {
            "count": feature_summary["count"],
            "enabled": feature_summary["enabled"],
            "available": feature_summary["available"],
            "failed": feature_summary["failed"],
            "activation_blocked": feature_summary["activation_blocked"],
        },
        "providers": {
            name: {"registered": ProviderRegistry.get(name) is not None}
            for name in PROVIDER_STATUS_NAMES
        },
        "security": {
            "project_terminal_execution": "disabled",
            "sandbox_verification": "not_implemented",
        },
    }


@router.get("/intelligence/history")
def intelligence_history(
    session_id: str | None = Query(default=None, max_length=128),
    project_id: str | None = Query(default=None, max_length=100),
    success: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    history = PipelineHistoryService()
    records = history.query(
        session_id=session_id,
        project_id=project_id,
        success=success,
        limit=limit,
        newest_first=True,
    )
    return {
        "success": True,
        "count": len(records),
        "stats": history.stats(),
        "history": records,
    }


@router.post("/intelligence/analyze")
def analyze_input(request: AnalyzeRequest):
    """Return deterministic intent, language, and mode analysis without executing a command."""
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text must not be blank")
    mode = ModeDetectionService().detect(text)
    return {
        "success": True,
        "intent": IntentClassifierService().classify(text),
        "language": LanguageDetectionService().detect(text),
        "mode": mode.model_dump(mode="json"),
        "execution_started": False,
    }


@router.get("/modes")
def list_modes(session_id: str | None = None):
    registry = ModeRegistryService()
    active_mode = "auto"
    if session_id:
        session = SessionManagerService().get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        active_mode = session.get("active_mode") or "auto"
    return {
        "success": True,
        "active_mode": active_mode,
        "count": registry.count(),
        "modes": [mode.model_dump(mode="json") for mode in registry.get_all()],
    }


@router.post("/modes/select")
def select_mode(request: SelectModeRequest):
    sessions = SessionManagerService()
    session = sessions.get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session.get("status") != "active":
        raise HTTPException(status_code=409, detail="session must be active before changing its mode")

    mode_id = request.mode_id.strip().lower()
    if mode_id == "auto":
        updated = sessions.update_context(request.session_id, active_mode=None)
        return {
            "success": True,
            "session_id": updated["session_id"],
            "active_mode": "auto",
            "mode": None,
        }

    registry = ModeRegistryService()
    mode = registry.get(mode_id)
    if mode is None:
        raise HTTPException(status_code=404, detail="mode not found")

    updated = sessions.update_context(
        request.session_id,
        active_mode=mode.id,
    )
    return {
        "success": True,
        "session_id": updated["session_id"],
        "active_mode": mode.id,
        "mode": mode.model_dump(mode="json"),
    }
