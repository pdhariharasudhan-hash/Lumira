"""
goal_module.py

BrainModule implementation for the Goal Manager.

This module updates the runtime GoalState
inside BrainState.

Ownership:
Handoff 11 - Goal Manager
"""

from app.services.brain.brain_module import BrainModule
from app.services.brain.brain_state import BrainState

from app.services.goals.goal_service import (
    GoalService,
)


class GoalModule(BrainModule):
    """
    Brain module responsible for identifying
    the user's primary goal.
    """

    def __init__(self):

        self.service = GoalService()

    @property
    def name(self) -> str:

        return "goal"

    @property
    def order(self) -> int:

        return 2

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute the Goal Manager stage.
        """

        user_input = state.context.get(
            "user_input",
            "",
        )

        if not user_input:
            return state

        state.goal = self.service.analyze(
            user_input=user_input,
            state=state.goal,
        )

        return state