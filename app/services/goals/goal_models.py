"""
goal_models.py

Defines the runtime Goal State for Lumira's
Intelligence Layer.

GoalState exists only during a Brain execution.

It is NOT permanent memory.

Ownership:
Handoff 11 - Goal Manager
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class GoalState(BaseModel):
    """
    Runtime representation of the user's current goal.

    This model is owned exclusively by the Goal Manager.
    """

    primary_goal: str = ""

    goal_type: str = ""

    goal_category: str = ""

    priority: str = "normal"

    is_long_term: bool = False

    completed: bool = False

    confidence: float = 0.0

    identified_at: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    )