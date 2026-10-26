"""
constraint_module.py

BrainModule implementation for the Constraint Analysis Engine.

This module updates the runtime ConstraintState
inside BrainState.

Ownership:
Handoff 11 - Constraint Analysis
"""

from app.services.brain.brain_module import BrainModule
from app.services.brain.brain_state import BrainState

from app.services.constraints.constraint_service import (
    ConstraintService,
)


class ConstraintModule(BrainModule):
    """
    Brain module responsible for analyzing
    all constraints affecting execution.
    """

    def __init__(self):

        self.service = ConstraintService()

    @property
    def name(self) -> str:

        return "constraints"

    @property
    def order(self) -> int:

        return 5

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute the Constraint Analysis stage.
        """

        state.constraints = self.service.analyze(
            conversation=state.conversation,
            goal=state.goal,
            objective=state.objective,
            context=state.context,
            state=state.constraints,
        )

        return state