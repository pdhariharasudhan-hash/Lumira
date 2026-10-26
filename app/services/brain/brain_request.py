"""
brain_request.py

Standard request object for a Brain execution.

BrainRequest contains the user request and the execution-level
context required to initialize a Brain run.

It does not contain cognitive state.

Ownership:
Handoff 12 - Brain Integration
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BrainRequest(BaseModel):
    """
    Input received by the Brain before cognitive execution.

    BrainRequest contains only request-level information.

    Cognitive state belongs to BrainState.
    Execution metadata belongs to BrainContext.
    """

    # ----------------------------------
    # User Request
    # ----------------------------------

    message: str = Field(default="", max_length=100_000)

    # ----------------------------------
    # Execution Context
    # ----------------------------------

    project: Optional[str] = None

    session_id: str = ""

    environment: str = "development"

    workspace: str = "default"

    # ----------------------------------
    # Additional Metadata
    # ----------------------------------

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )