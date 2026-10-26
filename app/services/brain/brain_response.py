"""
brain_response.py

Standard response object returned after Brain execution.

Ownership:
Handoff 12 - Brain Integration
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.services.brain.brain_state import BrainState


class BrainResponse(BaseModel):
    """
    Standard result returned by the Brain.
    """

    success: bool = True

    state: Optional[BrainState] = None

    trace: list[Dict[str, Any]] = Field(
        default_factory=list
    )

    error: Optional[str] = None