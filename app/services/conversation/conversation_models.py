"""
conversation_models.py

Defines the runtime conversation state for Lumira's
Intelligence Layer.

ConversationState is temporary.

It exists only during a Brain execution and is stored
inside BrainState.

Ownership:
Handoff 11 - Conversation Intelligence
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class ConversationState(BaseModel):
    """
    Runtime state for the active conversation.

    This model is NOT permanent memory.

    It tracks only the current conversation while
    the Brain pipeline is executing.
    """

    current_topic: str = ""

    current_goal: str = ""

    conversation_summary: str = ""

    pending_questions: List[str] = Field(
        default_factory=list
    )

    topic_history: List[str] = Field(
        default_factory=list
    )

    mentioned_projects: List[str] = Field(
        default_factory=list
    )

    mentioned_features: List[str] = Field(
        default_factory=list
    )

    detected_entities: List[str] = Field(
        default_factory=list
    )

    detected_intent: str = ""

    detected_language: str = "en"

    confidence: float = 0.0

    last_updated: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )