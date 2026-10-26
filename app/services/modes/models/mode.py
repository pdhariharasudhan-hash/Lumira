from typing import Dict, List

from pydantic import BaseModel, Field


class ModeDefinition(BaseModel):
    """
    Structured definition of a Lumira operating mode.

    A mode is an operating configuration of the same Lumira Core.
    It is not a separate AI or intelligence system.

    Ownership:
    Handoff 13 - Mode Architecture
    """

    id: str

    name: str

    description: str

    priority_capabilities: List[str] = Field(
        default_factory=list
    )

    restricted_capabilities: List[str] = Field(
        default_factory=list
    )

    context_rules: Dict[str, str] = Field(
        default_factory=dict
    )

    activation_rules: List[str] = Field(
        default_factory=list
    )
