"""
verification_models.py

Defines the runtime Verification State.

VerificationState exists only during a Brain execution.

Ownership:
Handoff 11 - Verification Engine
"""

from datetime import datetime

from pydantic import BaseModel, Field


class VerificationState(BaseModel):
    """
    Runtime verification generated for
    the current execution plan.
    """

    validation_rules: list[str] = Field(
        default_factory=list
    )

    required_checks: list[str] = Field(
        default_factory=list
    )

    passed_checks: list[str] = Field(
        default_factory=list
    )

    failed_checks: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    ready_for_execution: bool = False

    confidence: float = 0.0

    verified_at: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )