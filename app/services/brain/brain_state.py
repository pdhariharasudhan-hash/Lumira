"""
brain_state.py

Temporary cognitive state used during a single Brain pipeline execution.

BrainState is NOT permanent memory.

It is recreated for every request and passed between the
Intelligence Layer modules.

Ownership:
Handoff 12 - Brain Integration
"""

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from pydantic import BaseModel, Field

from app.services.conversation.conversation_models import (
    ConversationState,
)

from app.services.goals.goal_models import (
    GoalState,
)

from app.services.objective.objective_models import (
    ObjectiveState,
)

from app.services.context.context_models import (
    ContextState,
)

from app.services.constraints.constraint_models import (
    ConstraintState,
)

from app.services.reasoning.reasoning_models import (
    ReasoningState,
)

from app.services.decision.decision_models import (
    DecisionState,
)


class BrainMetadata(BaseModel):
    """
    Metadata describing the current Brain execution.
    """

    execution_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    pipeline_version: str = "1.0"

    brain_version: str = "handoff_12"

    started_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class BrainState(BaseModel):
    """
    Temporary working memory for Lumira.

    Every Brain execution receives a fresh BrainState.

    Raw user input is stored separately from derived
    Intelligence Layer states.

    Conversation Module
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

    # ----------------------------------
    # Raw Execution Input
    # ----------------------------------

    user_input: str = ""

    # ----------------------------------
    # Strongly Typed Intelligence States
    # ----------------------------------

    conversation: ConversationState = Field(
        default_factory=ConversationState
    )

    goal: GoalState = Field(
        default_factory=GoalState
    )

    objective: ObjectiveState = Field(
        default_factory=ObjectiveState
    )

    context: ContextState = Field(
        default_factory=ContextState
    )

    constraints: ConstraintState = Field(
        default_factory=ConstraintState
    )

    reasoning: ReasoningState = Field(
        default_factory=ReasoningState
    )

    decision: DecisionState = Field(
        default_factory=DecisionState
    )

    # ----------------------------------
    # Remaining Intelligence States
    # ----------------------------------

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

    # ----------------------------------
    # Execution Metadata
    # ----------------------------------

    metadata: BrainMetadata = Field(
        default_factory=BrainMetadata
    )

    def reset(self) -> None:
        """
        Reset the BrainState for a fresh pipeline execution.
        """

        self.user_input = ""

        self.conversation = ConversationState()

        self.goal = GoalState()

        self.objective = ObjectiveState()

        self.context = ContextState()

        self.constraints = ConstraintState()

        self.reasoning = ReasoningState()

        self.decision = DecisionState()

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