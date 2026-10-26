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

                mode=state.mode,
            )
        )

        state.plan = {
            "execution_steps": list(state.planner.execution_steps),
            "dependencies": list(state.planner.dependencies),
            "priorities": list(state.planner.priorities),
            "milestones": list(state.planner.milestones),
            "execution_order": list(state.planner.execution_order),
            "completion_criteria": list(state.planner.completion_criteria),
            "confidence": state.planner.confidence,
        }

        return state