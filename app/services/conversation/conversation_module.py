"""
conversation_module.py

BrainModule implementation for Conversation Intelligence.

This module updates the runtime ConversationState
inside BrainState.

Ownership:
Handoff 12 - Brain Integration
"""

from app.services.brain.brain_module import (
    BrainModule,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.conversation.conversation_service import (
    ConversationService,
)


class ConversationModule(BrainModule):
    """
    Brain module responsible for maintaining
    the active conversation state.
    """

    def __init__(self):

        self.service = ConversationService()

    @property
    def name(self) -> str:

        return "conversation"

    @property
    def order(self) -> int:

        return 1

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute the Conversation Intelligence stage.
        """

        state.conversation = (
            self.service.analyze(
                user_input=state.user_input,
                state=state.conversation,
            )
        )

        return state