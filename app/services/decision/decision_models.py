"""
decision_models.py

Defines the runtime Decision State for Lumira's
Intelligence Layer.

DecisionState exists only during a Brain execution.

It is NOT permanent memory.

Ownership:
Handoff 11 - Decision Engine
"""

from datetime import datetime

from pydantic import BaseModel, Field


class DecisionState(BaseModel):
    """
    Runtime representation of Lumira's
    decision-making process.

    This model is owned exclusively by the
    Decision Engine.
    """

    selected_option: str = ""

    decision_reason: str = ""

    alternatives_considered: list[str] = Field(
        default_factory=list
    )

    accepted_constraints: list[str] = Field(
        default_factory=list
    )

    rejected_constraints: list[str] = Field(
        default_factory=list
    )

    tradeoffs: list[str] = Field(
        default_factory=list
    )

    next_action: str = ""

    confidence: float = 0.0

    decided_at: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )