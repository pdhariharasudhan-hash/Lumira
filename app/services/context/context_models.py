"""
context_models.py

Defines the runtime Context State for Lumira's
Intelligence Layer.

ContextState exists only during a Brain execution.

It is NOT permanent memory.

Ownership:
Handoff 11 - Context Engine
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ContextState(BaseModel):
    """
    Runtime execution context.

    Stores the information needed by later
    intelligence modules.
    """

    project_type: str = ""

    domain: str = ""

    programming_language: str = ""

    framework: str = ""

    environment: str = "development"

    workspace: str = "default"

    existing_project: bool = False

    confidence: float = 0.0

    identified_at: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    )