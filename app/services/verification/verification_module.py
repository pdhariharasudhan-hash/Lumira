"""
verification_module.py

BrainModule implementation for the
Verification Engine.

Ownership:
Handoff 11 - Verification Engine
"""

from app.services.brain.brain_module import (
    BrainModule,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.verification.verification_service import (
    VerificationService,
)


class VerificationModule(
    BrainModule
):

    def __init__(self):

        self.service = (
            VerificationService()
        )

    @property
    def name(self):

        return "verification"

    @property
    def order(self):

        return 10

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:

        state.verification = (
            self.service.analyze(

                prediction=state.prediction,

                planner=state.planner,

                state=state.verification,
            )
        )

        return state