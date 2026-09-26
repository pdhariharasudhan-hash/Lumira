"""
decision_module.py

BrainModule implementation for the Decision Engine.

This module updates the runtime DecisionState
inside BrainState.

Ownership:
Handoff 11 - Decision Engine
"""

from app.services.brain.brain_module import BrainModule
from app.services.brain.brain_state import BrainState

from app.services.decision.decision_service import (
    DecisionService,
)


class DecisionModule(BrainModule):
    """
    Brain module responsible for selecting
    the best execution path based on
    reasoning results.
    """

    def __init__(self):

        self.service = DecisionService()

    @property
    def name(self) -> str:

        return "decision"

    @property
    def order(self) -> int:

        return 7

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute the Decision Engine.
        """

        state.decision = self.service.analyze(
            reasoning=state.reasoning,
            constraints=state.constraints,
            state=state.decision,
            mode=state.mode,
        )

        return state