"""
reflection_module.py

BrainModule implementation
for Reflection Engine.
"""

from app.services.brain.brain_module import (
    BrainModule,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.reflection.reflection_service import (
    ReflectionService,
)


class ReflectionModule(
    BrainModule
):

    def __init__(self):

        self.service = (
            ReflectionService()
        )

    @property
    def name(self):

        return "reflection"

    @property
    def order(self):

        return 11

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:

        state.reflection = (
            self.service.analyze(

                verification=state.verification,

                prediction=state.prediction,

                state=state.reflection,

                mode=state.mode,
            )
        )

        return state