"""
prediction_models.py

Defines the runtime Prediction State.

PredictionState exists only during a Brain execution.

Ownership:
Handoff 11 - Prediction Engine
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PredictionState(BaseModel):
    """
    Runtime prediction generated from the
    current execution plan.
    """

    expected_outcomes: list[str] = Field(
        default_factory=list
    )

    success_probability: float = 0.0

    failure_probability: float = 0.0

    identified_risks: list[str] = Field(
        default_factory=list
    )

    bottlenecks: list[str] = Field(
        default_factory=list
    )

    estimated_duration: str = ""

    estimated_complexity: str = ""

    confidence: float = 0.0

    predicted_at: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )