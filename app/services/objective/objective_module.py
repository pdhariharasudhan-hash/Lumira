"""
objective_module.py

BrainModule implementation for Objective Extraction.

This module updates the runtime ObjectiveState
inside BrainState.

Raw user input is provided by BrainState.user_input.

Ownership:
Handoff 12 - Brain Integration
"""

from app.services.brain.brain_module import (
    BrainModule,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.objective.objective_service import (
    ObjectiveService,
)


class ObjectiveModule(BrainModule):
    """
    Brain module responsible for determining
    the concrete objective of the user's request.
    """

    def __init__(self):

        self.service = ObjectiveService()

    @property
    def name(self) -> str:

        return "objective"

    @property
    def order(self) -> int:

        return 3

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute the Objective Extraction stage.
        """

        user_input = state.user_input

        if not user_input:
            return state

        state.objective = self.service.analyze(
            user_input=user_input,
            state=state.objective,
        )

        return state