"""
brain_registry.py

Central registry for Lumira's Intelligence Layer modules.

The registry defines the deterministic execution order of the
cognitive modules and provides them to the Brain pipeline.

Ownership:
Handoff 12 - Brain Integration
"""

from typing import List

from app.services.brain.brain_module import BrainModule

from app.services.conversation.conversation_module import (
    ConversationModule,
)

from app.services.goals.goal_module import (
    GoalModule,
)

from app.services.objective.objective_module import (
    ObjectiveModule,
)

from app.services.context.context_module import (
    ContextModule,
)

from app.services.constraints.constraint_module import (
    ConstraintModule,
)

from app.services.reasoning.reasoning_module import (
    ReasoningModule,
)

from app.services.decision.decision_module import (
    DecisionModule,
)

from app.services.planner.planner_module import (
    PlannerModule,
)

from app.services.prediction.prediction_module import (
    PredictionModule,
)

from app.services.verification.verification_module import (
    VerificationModule,
)

from app.services.reflection.reflection_module import (
    ReflectionModule,
)

from app.services.learning.learning_module import (
    LearningModule,
)


class BrainRegistry:
    """
    Registry containing all Intelligence Layer modules.

    Module order is deterministic and represents the official
    cognitive execution sequence for Handoff 12.
    """

    def __init__(self) -> None:
        self._modules: List[BrainModule] = [
            ConversationModule(),
            GoalModule(),
            ObjectiveModule(),
            ContextModule(),
            ConstraintModule(),
            ReasoningModule(),
            DecisionModule(),
            PlannerModule(),
            PredictionModule(),
            VerificationModule(),
            ReflectionModule(),
            LearningModule(),
        ]

    def get_modules(self) -> List[BrainModule]:
        """
        Return all registered modules in deterministic execution order.
        """

        return list(self._modules)

    def get_module_names(self) -> List[str]:
        """
        Return the class names of all registered modules.
        """

        return [
            module.__class__.__name__
            for module in self._modules
        ]

    def count(self) -> int:
        """
        Return the number of registered Intelligence modules.
        """

        return len(self._modules)