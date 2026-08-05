"""
reasoning_models.py

Defines the runtime Reasoning State for Lumira's
Intelligence Layer.

ReasoningState exists only during a Brain execution.

It is NOT permanent memory.

Ownership:
Handoff 11 - Reasoning Engine
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ReasoningState(BaseModel):
    """
    Runtime representation of Lumira's reasoning.

    This model is owned exclusively by the
    Reasoning Engine.
    """

    facts: list[str] = Field(
        default_factory=list
    )

    assumptions: list[str] = Field(
        default_factory=list
    )

    alternatives: list[str] = Field(
        default_factory=list
    )

    conclusions: list[str] = Field(
        default_factory=list
    )

    unresolved_questions: list[str] = Field(
        default_factory=list
    )

    reasoning_trace: list[str] = Field(
        default_factory=list
    )

    confidence: float = 0.0

    identified_at: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )