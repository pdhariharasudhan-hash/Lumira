"""
brain_state.py

Temporary cognitive state used during a single Brain pipeline execution.

BrainState is NOT permanent memory.

It is recreated for every request and passed between the
Intelligence Layer modules.

BrainState contains both:

1. Execution context
   -> BrainContext

2. Cognitive intelligence states
   -> ConversationState
   -> GoalState
   -> ObjectiveState
   -> ContextState
   -> ConstraintState
   -> ReasoningState
   -> DecisionState
   -> PlannerState
   -> PredictionState
   -> VerificationState
   -> ReflectionState
   -> LearningState

Ownership:
Handoff 12 - Intelligence Layer
"""

from typing import Any, Dict

from pydantic import BaseModel, Field

from app.services.brain.brain_context import BrainContext

from app.services.modes.models.mode_state import (
    ModeState,
)

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

from app.services.planner.planner_models import (
    PlannerState,
)

from app.services.prediction.prediction_models import (
    PredictionState,
)

from app.services.verification.verification_models import (
    VerificationState,
)

from app.services.reflection.reflection_models import (
    ReflectionState,
)

from app.services.learning.learning_models import (
    LearningState,
)


class BrainMetadata(BaseModel):
    """
    Metadata describing the current Brain execution.
    """

    pipeline_version: str = "1.0"

    brain_version: str = "handoff_12"


class BrainState(BaseModel):
    """
    Temporary working memory for Lumira.

    Every Brain module owns exactly ONE cognitive section.

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
        -> planner

    Prediction Engine
        -> prediction

    Verification Engine
        -> verification

    Reflection Engine
        -> reflection

    Learning Engine
        -> learning

    Execution-level metadata belongs to:
        -> execution_context
    """

    # ----------------------------------
    # Execution Context
    # ----------------------------------

    execution_context: BrainContext = Field(
        default_factory=BrainContext
    )

    # ----------------------------------
    # Original User Input
    # ----------------------------------

    user_input: str = ""

    # ----------------------------------
    # Operating Mode State
    # ----------------------------------

    mode: ModeState = Field(
        default_factory=ModeState
    )

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

    planner: PlannerState = Field(
        default_factory=PlannerState
    )

    prediction: PredictionState = Field(
        default_factory=PredictionState
    )

    verification: VerificationState = Field(
        default_factory=VerificationState
    )

    reflection: ReflectionState = Field(
        default_factory=ReflectionState
    )

    learning: LearningState = Field(
        default_factory=LearningState
    )

    # ----------------------------------
    # Brain Metadata
    # ----------------------------------

    metadata: BrainMetadata = Field(
        default_factory=BrainMetadata
    )

    # ----------------------------------
    # Reset
    # ----------------------------------

    def reset(self) -> None:
        """
        Reset the BrainState for a fresh pipeline execution.
        """

        self.execution_context = BrainContext()

        self.user_input = ""

        self.mode = ModeState()

        self.conversation = ConversationState()

        self.goal = GoalState()

        self.objective = ObjectiveState()

        self.context = ContextState()

        self.constraints = ConstraintState()

        self.reasoning = ReasoningState()

        self.decision = DecisionState()

        self.planner = PlannerState()

        self.prediction = PredictionState()

        self.verification = VerificationState()

        self.reflection = ReflectionState()

        self.learning = LearningState()

        self.metadata = BrainMetadata()

    # ----------------------------------
    # Serialization
    # ----------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Export BrainState as a dictionary.
        """

        return self.model_dump()