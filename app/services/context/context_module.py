"""
context_module.py

BrainModule implementation for the Context Engine.

This module updates the runtime ContextState
inside BrainState.

Ownership:
Handoff 11 - Context Engine
"""

from app.services.brain.brain_module import BrainModule
from app.services.brain.brain_state import BrainState

from app.services.context.context_service import (
    ContextService,
)


class ContextModule(BrainModule):
    """
    Brain module responsible for determining
    the execution context.
    """

    def __init__(self):

        self.service = ContextService()

    @property
    def name(self) -> str:

        return "context"

    @property
    def order(self) -> int:

        return 4

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute the Context Engine.
        """

        state.context = self.service.analyze(

            conversation=state.conversation,

            goal=state.goal,

            objective=state.objective,

            state=state.context,
        )
        state.context.existing_project = bool(
            state.execution_context.project_id
        )
        state.context.workspace = state.execution_context.workspace

        return state