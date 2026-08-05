"""
planner_models.py

Defines the runtime Planner State.

PlannerState exists only during a Brain execution.

Ownership:
Handoff 11 - Planner Intelligence
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PlannerState(BaseModel):
    """
    Runtime representation of Lumira's execution plan.
    """

    execution_steps: list[str] = Field(
        default_factory=list
    )

    dependencies: list[str] = Field(
        default_factory=list
    )

    priorities: list[str] = Field(
        default_factory=list
    )

    milestones: list[str] = Field(
        default_factory=list
    )

    estimated_outputs: list[str] = Field(
        default_factory=list
    )

    execution_order: list[str] = Field(
        default_factory=list
    )

    parallel_tasks: list[str] = Field(
        default_factory=list
    )

    blocked_tasks: list[str] = Field(
        default_factory=list
    )

    completion_criteria: list[str] = Field(
        default_factory=list
    )

    confidence: float = 0.0

    created_at: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )