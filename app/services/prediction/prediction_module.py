"""
prediction_module.py

BrainModule implementation for the
Prediction Engine.

Ownership:
Handoff 11 - Prediction Engine
"""

from app.services.brain.brain_module import (
    BrainModule,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.prediction.prediction_service import (
    PredictionService,
)


class PredictionModule(
    BrainModule
):

    def __init__(self):

        self.service = (
            PredictionService()
        )

    @property
    def name(self):

        return "prediction"

    @property
    def order(self):

        return 9

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:

        state.prediction = (
            self.service.analyze(

                planner=state.planner,

                decision=state.decision,

                state=state.prediction,

                mode=state.mode,
            )
        )

        return state