"""
planner_module.py

BrainModule implementation for Planner Intelligence.

Ownership:
Handoff 11 - Planner Intelligence
"""

from app.services.brain.brain_module import (
    BrainModule,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.planner.planner_service import (
    PlannerService,
)


class PlannerModule(
    BrainModule
):

    def __init__(self):

        self.service = (
            PlannerService()
        )

    @property
    def name(self):

        return "planner"

    @property
    def order(self):

        return 8

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:

        state.planner = (
            self.service.analyze(

                decision=state.decision,

                reasoning=state.reasoning,

                state=state.planner,
            )
        )

        return state