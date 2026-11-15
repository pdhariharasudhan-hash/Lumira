from __future__ import annotations

import re
from typing import Any

from app.services.command_parser_service import CommandParserService
from app.services.language.language_detection_service import LanguageDetectionService


class IntentClassifierService:
    """Deterministic English, Tamil-script and romanized-Tamil intent classifier."""

    MAX_COMMAND_CHARS = 10_000
    TAMIL_PHRASES = {
        "build": (
            "உருவாக்கு", "உருவாக்குங்கள்", "கட்டு", "கட்டுங்கள்",
            "செய்து கொடு", "செய்து தா", "தயாரி", "தயாரிக்கவும்",
        ),
        "continue": (
            "தொடர்", "தொடரவும்", "தொடருங்கள்", "தொடரு",
        ),
        "search": (
            "தேடு", "தேடுங்கள்", "கண்டுபிடி", "கண்டுபிடிக்கவும்",
        ),
        "show": (
            "காட்டு", "காட்டுங்கள்", "காண்பி", "காண்பிக்கவும்",
        ),
        "plan": (
            "திட்டமிடு", "திட்டமிடுங்கள்", "திட்டம் போடு", "திட்டம்",
        ),
        "research": (
            "ஆராய்ச்சி", "ஆராய்ந்து பார்", "ஆய்வு செய்",
        ),
        "personal": (
            "நினைவில் வை", "நினைவில் வைத்துக்கொள்", "நினைவூட்டு",
        ),
        "mode": (
            "முறையை மாற்று", "மோடை மாற்று", "பயன்முறையை மாற்று",
        ),
    }

    ROMANIZED_PHRASES = {
        "build": (
            "uruvakku", "uruvakkunga", "kattu", "kattunga",
            "build pannu", "create pannu", "seithu kudu", "seythu kudu",
            "panni kudu", "thayaar pannu",
        ),
        "continue": (
            "thodar", "thodaru", "thodarunga", "thodara vum",
            "continue pannu", "continue pannunga",
        ),
        "search": (
            "thedu", "thedunga", "thedi paaru", "kandu pidi",
            "kandupid i", "search pannu",
        ),
        "show": (
            "kaatu", "kaaminga", "kaattunga", "kaami",
            "show pannu", "kaatti kudu",
        ),
        "plan": (
            "thittam", "thittamidu", "thittam podu", "plan pannu",
        ),
        "research": (
            "aaraichi", "araichi", "aayvu pannu", "research pannu",
        ),
        "personal": (
            "nyabagam vai", "ninaivil vai", "nyabagam vechuko",
        ),
        "mode": (
            "mode maathu", "mode change pannu", "mode ku maathu",
        ),
    }

    ENGLISH_PREFIXES = (
        (("enter ", "switch to ", "change to ", "set "), "mode"),
        (("build", "create", "implement", "develop", "code", "generate project"), "build"),
        (("add ", "continue", "resume", "keep going"), "continue"),
        (("search", "find ", "look up "), "search"),
        (("show", "list", "display"), "show"),
        (("plan", "schedule", "roadmap"), "plan"),
        (("research", "investigate", "compare", "analyze", "analyse"), "research"),
    )

    PARSED_CATEGORIES = {
        "activate_mode": "mode",
        "search": "search",
        "list_features": "show",
        "resume_project": "continue",
        "continue_project": "continue",
        "project_generation": "build",
        "project_engineering": "build",
        "project_versioning": "build",
        "debugging": "build",
        "technical_research": "research",
        "knowledge_retrieval": "research",
        "research": "research",
        "comparison": "research",
        "web_access": "research",
        "business_plan": "plan",
        "planning": "plan",
        "goals": "plan",
        "tasks": "plan",
        "growth_strategy": "plan",
        "product_improvement": "plan",
        "user_growth": "plan",
        "optimization": "plan",
        "market_analysis": "research",
        "revenue_analysis": "research",
        "competitive_analysis": "research",
        "business_operations": "operations",
        "workflow_automation": "operations",
        "scheduled_tasks": "operations",
        "monitoring": "operations",
        "activate_feature": "control",
        "activate_feature_with_dependencies": "control",
        "feature_dependency_plan": "control",
        "feature_status": "control",
        "deactivate_feature": "control",
        "generate_image": "create",
        "image_generation": "create",
        "video_generation": "create",
        "document_generation": "create",
        "presentations": "create",
        "posters": "create",
        "thumbnails": "create",
        "scripts": "create",
        "marketing_assets": "create",
        "content_planning": "create",
        "diagram_generation": "create",
        "architecture_diagrams": "create",
        "flowcharts": "create",
        "blueprint_generation": "create",
        "schematic_generation": "create",
        "ui_design": "create",
        "personal_context": "personal",
        "notes": "personal",
        "reminders": "personal",
        "scheduling": "personal",
        "daily_planning": "plan",
        "notifications": "personal",
        "personal_organization": "personal",
        "email": "personal",
        "voice": "personal",
        "project_pipeline": "build",
    }

    def __init__(self, parser=None, language_detector=None):
        self.parser = parser or CommandParserService()
        self.language_detector = language_detector or LanguageDetectionService()

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        normalized_phrase = " ".join(phrase.casefold().split())
        if not normalized_phrase:
            return False
        if any("\u0B80" <= char <= "\u0BFF" for char in normalized_phrase):
            return normalized_phrase in text
        return re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])",
            text,
        ) is not None

    def classify_detailed(self, command: str) -> dict[str, Any]:
        if not isinstance(command, str) or not command.strip() or len(command) > self.MAX_COMMAND_CHARS:
            return {
                "success": False,
                "intent": "chat",
                "language": "unknown",
                "confidence": 0.0,
                "source": "invalid_input",
            }

        raw = command.strip()
        normalized = " ".join(raw.casefold().split())
        language = self.language_detector.detect(raw)
        language_code = language.get("language", "unknown") if isinstance(language, dict) else "unknown"

        # Tamil-script phrases take priority over broad English keyword matching.
        for intent, phrases in self.TAMIL_PHRASES.items():
            if any(self._contains_phrase(normalized, phrase) for phrase in phrases):
                return {"success": True, "intent": intent, "language": language_code, "confidence": 0.95, "source": "tamil_script_phrase"}

        for intent, phrases in self.ROMANIZED_PHRASES.items():
            if any(self._contains_phrase(normalized, phrase) for phrase in phrases):
                return {"success": True, "intent": intent, "language": language_code, "confidence": 0.88, "source": "romanized_tamil_phrase"}

        if "enter " in normalized and " mode" in normalized:
            return {"success": True, "intent": "mode", "language": language_code, "confidence": 0.98, "source": "english_prefix"}
        for prefixes, intent in self.ENGLISH_PREFIXES:
            if normalized.startswith(prefixes):
                return {"success": True, "intent": intent, "language": language_code, "confidence": 0.96, "source": "english_prefix"}

        try:
            parsed = self.parser.parse(raw)
        except Exception:
            parsed = None
        if not isinstance(parsed, dict) or parsed.get("success") is not True:
            return {"success": True, "intent": "chat", "language": language_code, "confidence": 0.55, "source": "fallback"}

        capability = parsed.get("capability")
        if not isinstance(capability, str) or not capability.strip():
            return {"success": True, "intent": "chat", "language": language_code, "confidence": 0.55, "source": "fallback"}
        capability = capability.strip().lower()
        payload = parsed.get("payload", {})
        if capability == "agent_task":
            agent_name = payload.get("agent_name") if isinstance(payload, dict) else None
            intent = {
                "code_agent": "build",
                "planner_agent": "plan",
                "research_agent": "research",
            }.get(agent_name, "agent")
        else:
            intent = self.PARSED_CATEGORIES.get(capability, "chat")
        return {
            "success": True,
            "intent": intent,
            "language": language_code,
            "confidence": 0.86 if intent != "chat" else 0.6,
            "source": "command_parser",
            "capability": capability,
        }

    def classify(self, command: str) -> str:
        """Backward-compatible intent-only result."""
        return self.classify_detailed(command).get("intent", "chat")
