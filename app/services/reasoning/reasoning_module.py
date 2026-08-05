"""
reasoning_module.py

BrainModule implementation for the Reasoning Engine.

This module updates the runtime ReasoningState
inside BrainState.

Ownership:
Handoff 11 - Reasoning Engine
"""

from app.services.brain.brain_module import BrainModule
from app.services.brain.brain_state import BrainState

from app.services.reasoning.reasoning_service import (
    ReasoningService,
)


class ReasoningModule(BrainModule):
    """
    Brain module responsible for deriving
    logical conclusions from the collected
    intelligence.
    """

    def __init__(self):

        self.service = ReasoningService()

    @property
    def name(self) -> str:

        return "reasoning"

    @property
    def order(self) -> int:

        return 6

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute the Reasoning Engine.
        """

        state.reasoning = self.service.analyze(
            conversation=state.conversation,
            goal=state.goal,
            objective=state.objective,
            context=state.context,
            constraints=state.constraints,
            state=state.reasoning,
        )

        return state
        