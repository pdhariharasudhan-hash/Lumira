"""
conversation_service.py

Implements the runtime Conversation Intelligence for Lumira.

This service analyzes the current user input and updates the
ConversationState.

It does NOT access Memory, Projects, Workspace, or BrainState.

Ownership:
Handoff 11 - Conversation Intelligence
"""

from datetime import datetime

from app.services.conversation.conversation_models import (
    ConversationState,
)
from app.services.language.intent_classifier_service import (
    IntentClassifierService,
)
from app.services.language.language_detection_service import (
    LanguageDetectionService,
)


class ConversationService:
    """
    Handles runtime conversation analysis.

    This service owns only ConversationState.
    """

    def __init__(self):
        self.intent_classifier = IntentClassifierService()
        self.language_detector = LanguageDetectionService()

    def analyze(
        self,
        user_input: str,
        state: ConversationState,
    ) -> ConversationState:
        """
        Analyze the current user input and update the
        ConversationState.
        """

        text = user_input.strip()

        if not text:
            return state

        # ---------------------------------
        # Topic Detection (Temporary)
        # ---------------------------------

        previous_summary = state.conversation_summary
        state.current_topic = text

        # ---------------------------------
        # Topic History
        # ---------------------------------

        if (
            not state.topic_history
            or state.topic_history[-1] != text
        ):
            state.topic_history.append(text)
            state.topic_history = state.topic_history[-20:]

        # ---------------------------------
        # Simple Goal Detection
        # ---------------------------------

        detected_goal = self._detect_goal(text)
        if detected_goal:
            state.current_goal = detected_goal

        # ---------------------------------
        # Conversation Summary
        # ---------------------------------

        current_summary = f"Current discussion: {state.current_topic}"
        state.conversation_summary = " | ".join(
            part for part in (previous_summary, current_summary) if part
        )[-2000:]

        # ---------------------------------
        # Intent Detection (Placeholder)
        # ---------------------------------

        state.detected_intent = self.intent_classifier.classify(text)

        # ---------------------------------
        # Language Detection
        # ---------------------------------

        language = self.language_detector.detect(text)
        state.detected_language = language["language"]

        # ---------------------------------
        # Confidence
        # ---------------------------------

        state.confidence = language["confidence"]

        # ---------------------------------
        # Timestamp
        # ---------------------------------

        state.last_updated = (
            datetime.utcnow().isoformat()
        )

        return state

    def _detect_goal(
        self,
        text: str,
    ) -> str:
        """
        Temporary goal detection.

        Will later be replaced by Goal Manager.
        """

        lowered = text.lower()

        keywords = [

            "build",

            "create",

            "make",

            "design",

            "develop",

            "generate"

        ]

        for keyword in keywords:

            if lowered.startswith(keyword):

                return text

        return ""

    def _detect_intent(
        self,
        text: str,
    ) -> str:
        """
        Temporary intent detection.

        Will later integrate with
        IntentClassifierService.
        """

        lowered = text.lower()

        if lowered.startswith("build"):
            return "build"

        if lowered.startswith("create"):
            return "create"

        if lowered.startswith("generate"):
            return "generate"

        if lowered.startswith("search"):
            return "search"

        if lowered.startswith("help"):
            return "help"

        return "conversation"