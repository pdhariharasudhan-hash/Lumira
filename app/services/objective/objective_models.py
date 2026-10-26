"""
objective_models.py

Defines the runtime Objective State for Lumira's
Intelligence Layer.

ObjectiveState exists only during a Brain execution.

It is NOT permanent memory.

Ownership:
Handoff 11 - Objective Extraction
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ObjectiveState(BaseModel):
    """
    Runtime representation of the user's objective.

    This model is owned exclusively by the
    Objective Extraction module.
    """

    primary_objective: str = ""

    expected_output: str = ""

    success_criteria: list[str] = Field(
        default_factory=list
    )

    dependencies: list[str] = Field(
        default_factory=list
    )

    completion_status: str = "pending"

    confidence: float = 0.0

    identified_at: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    )