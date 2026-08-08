"""
brain_request.py

Standard request object for a Brain execution.

Ownership:
Handoff 12 - Brain Integration
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BrainRequest(BaseModel):
    """
    Input received by the Brain before cognitive execution.
    """

    message: str = ""

    project: Optional[str] = None

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )