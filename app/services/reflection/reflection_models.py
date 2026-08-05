"""
reflection_models.py

Defines the runtime Reflection State.

Ownership:
Handoff 11 - Reflection Engine
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ReflectionState(BaseModel):

    observations: list[str] = Field(
        default_factory=list
    )

    strengths: list[str] = Field(
        default_factory=list
    )

    weaknesses: list[str] = Field(
        default_factory=list
    )

    missed_opportunities: list[str] = Field(
        default_factory=list
    )

    improvements: list[str] = Field(
        default_factory=list
    )

    overall_quality: str = ""

    confidence: float = 0.0

    reflected_at: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )