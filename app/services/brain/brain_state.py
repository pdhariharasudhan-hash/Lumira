"""
brain_state.py

Temporary cognitive state used during a single Brain pipeline execution.

BrainState is NOT permanent memory.

It is recreated for every request and passed between the
Intelligence Layer modules.

Ownership:
Handoff 11 - Intelligence Layer
"""

from typing import Any, Dict
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class BrainMetadata(BaseModel):
    """
    Metadata describing the current brain execution.
    """

    execution_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    pipeline_version: str = "1.0"

    brain_version: str = "handoff_11"

    started_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class BrainState(BaseModel):
    """
    Temporary working memory for the Brain.

    Each Intelligence module owns exactly ONE section.

    Conversation Intelligence
        -> conversation

    Goal Manager
        -> goal

    Objective Extraction
        -> objective

    Context Engine
        -> context

    Constraint Analysis
        -> constraints

    Reasoning Engine
        -> reasoning

    Decision Engine
        -> decision

    Planner Intelligence
        -> plan

    Prediction Engine
        -> prediction

    Verification Engine
        -> verification

    Reflection Engine
        -> reflection

    Learning Engine
        -> learning
    """

    conversation: Dict[str, Any] = Field(
        default_factory=dict
    )

    goal: Dict[str, Any] = Field(
        default_factory=dict
    )

    objective: Dict[str, Any] = Field(
        default_factory=dict
    )

    context: Dict[str, Any] = Field(
        default_factory=dict
    )

    constraints: Dict[str, Any] = Field(
        default_factory=dict
    )

    reasoning: Dict[str, Any] = Field(
        default_factory=dict
    )

    decision: Dict[str, Any] = Field(
        default_factory=dict
    )

    plan: Dict[str, Any] = Field(
        default_factory=dict
    )

    prediction: Dict[str, Any] = Field(
        default_factory=dict
    )

    verification: Dict[str, Any] = Field(
        default_factory=dict
    )

    reflection: Dict[str, Any] = Field(
        default_factory=dict
    )

    learning: Dict[str, Any] = Field(
        default_factory=dict
    )

    metadata: BrainMetadata = Field(
        default_factory=BrainMetadata
    )

    def reset(self) -> None:
        """
        Reset every cognitive section while
        preserving fresh metadata.
        """

        self.conversation.clear()
        self.goal.clear()
        self.objective.clear()
        self.context.clear()
        self.constraints.clear()
        self.reasoning.clear()
        self.decision.clear()
        self.plan.clear()
        self.prediction.clear()
        self.verification.clear()
        self.reflection.clear()
        self.learning.clear()

        self.metadata = BrainMetadata()

    def to_dict(self) -> Dict[str, Any]:
        """
        Export BrainState as a dictionary.
        """

        return self.model_dump()