"""
learning_module.py

BrainModule implementation
for Learning Engine.
"""

from app.services.brain.brain_module import (
    BrainModule,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.learning.learning_service import (
    LearningService,
)


class LearningModule(
    BrainModule
):

    def __init__(self):

        self.service = (
            LearningService()
        )

    @property
    def name(self):

        return "learning"

    @property
    def order(self):

        return 12

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:

        state.learning = (
            self.service.analyze(

                reflection=state.reflection,

                state=state.learning,
            )
        )

        return state