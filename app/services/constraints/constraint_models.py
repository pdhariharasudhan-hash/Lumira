"""
constraint_models.py

Defines the runtime Constraint State for Lumira's
Intelligence Layer.

ConstraintState exists only during a Brain execution.

It is NOT permanent memory.

Ownership:
Handoff 11 - Constraint Analysis
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ConstraintState(BaseModel):
    """
    Runtime representation of all constraints
    affecting the current request.

    This model is owned exclusively by the
    Constraint Analysis module.
    """

    # Functional requirements
    functional_constraints: list[str] = Field(
        default_factory=list
    )

    # Technical limitations
    technical_constraints: list[str] = Field(
        default_factory=list
    )

    # Hardware / Budget / Time
    resource_constraints: list[str] = Field(
        default_factory=list
    )

    # Platform requirements
    platform_constraints: list[str] = Field(
        default_factory=list
    )

    # Explicit user requirements
    user_constraints: list[str] = Field(
        default_factory=list
    )

    # Assumptions made by Lumira
    assumptions: list[str] = Field(
        default_factory=list
    )

    # Possible execution risks
    risks: list[str] = Field(
        default_factory=list
    )

    # Information still required
    missing_information: list[str] = Field(
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