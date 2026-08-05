"""
learning_models.py

Defines the runtime Learning State.

Ownership:
Handoff 11 - Learning Engine
"""

from datetime import datetime

from pydantic import BaseModel, Field


class LearningState(BaseModel):

    lessons: list[str] = Field(
        default_factory=list
    )

    successful_patterns: list[str] = Field(
        default_factory=list
    )

    failed_patterns: list[str] = Field(
        default_factory=list
    )

    recommendations: list[str] = Field(
        default_factory=list
    )

    knowledge_updates: list[str] = Field(
        default_factory=list
    )

    future_actions: list[str] = Field(
        default_factory=list
    )

    confidence: float = 0.0

    learned_at: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )