"""Language detection and multilingual intent APIs for Tamil/English commands."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.services.language.intent_classifier_service import IntentClassifierService
from app.services.language.language_detection_service import LanguageDetectionService

router = APIRouter(prefix="/language", tags=["Language"])
detector = LanguageDetectionService()
classifier = IntentClassifierService(language_detector=detector)


class LanguageTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: StrictStr = Field(min_length=1, max_length=10_000)


class LanguageBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texts: list[StrictStr] = Field(min_length=1, max_length=100)


@router.get("/capabilities")
def language_capabilities():
    return {
        "success": True,
        "languages": ["ta", "en", "ta-en"],
        "inputs": ["Tamil Unicode", "English", "romanized Tamil", "mixed Tamil-English"],
        "intent_labels": ["build", "continue", "search", "show", "plan", "research", "personal", "mode", "operations", "control", "create", "chat"],
        "note": "Tamil transliteration is lexicon-based and may return lower confidence than native Tamil script.",
    }


@router.post("/detect")
def detect_language(request: LanguageTextRequest):
    return {"success": True, **detector.detect(request.text)}


@router.post("/detect-many")
def detect_languages(request: LanguageBatchRequest):
    if any(not text.strip() or len(text) > 10_000 for text in request.texts):
        raise HTTPException(status_code=422, detail="Every text must contain 1 to 10000 characters.")
    return {"success": True, "results": detector.detect_many(request.texts)}


@router.post("/classify")
def classify_intent(request: LanguageTextRequest):
    return classifier.classify_detailed(request.text)


@router.post("/classify-many")
def classify_intents(request: LanguageBatchRequest):
    if any(not text.strip() or len(text) > 10_000 for text in request.texts):
        raise HTTPException(status_code=422, detail="Every text must contain 1 to 10000 characters.")
    return {
        "success": True,
        "results": [classifier.classify_detailed(text) for text in request.texts],
    }
