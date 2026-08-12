"""
brain_service.py

Main entry point for Lumira's Intelligence Layer.

BrainService coordinates the complete Brain execution flow.

It does not contain cognitive intelligence itself.

Flow:

BrainRequest
    ↓
BrainState
    ↓
BrainValidator
    ↓
BrainPipeline
    ↓
BrainExecutor
    ↓
BrainResponse

Ownership:
Handoff 12 - Brain Integration
"""

from typing import Optional

from app.services.brain.brain_factory import (
    BrainFactory,
)

from app.services.brain.brain_request import (
    BrainRequest,
)

from app.services.brain.brain_response import (
    BrainResponse,
)

from app.services.brain.brain_state import (
    BrainState,
)


class BrainService:
    """
    Main public orchestrator for Lumira's Brain.
    """

    def __init__(self) -> None:

        components = (
            BrainFactory.create_brain_components()
        )

        self.registry = components["registry"]

        self.executor = components["executor"]

        self.validator = components["validator"]

        self.pipeline = (
            self._create_pipeline()
        )

    def _create_pipeline(self):
        """
        Create the BrainPipeline using the shared executor.
        """

        from app.services.brain.brain_pipeline import (
            BrainPipeline,
        )

        return BrainPipeline(
            executor=self.executor
        )

    def create_state(
        self,
        request: Optional[BrainRequest] = None,
    ) -> BrainState:
        """
        Create a fresh temporary BrainState.

        Request data is mapped into the correct
        BrainState boundaries.

        User input:
            request.message
                -> state.user_input

        Project:
            request.project
                -> state.execution_context.project_id

        Metadata:
            request.metadata
                -> state.execution_context.metadata
        """

        state = BrainState()

        if request is None:
            return state

        # ----------------------------------
        # User Input
        # ----------------------------------

        state.user_input = request.message

        # ----------------------------------
        # Execution Context
        # ----------------------------------

        if request.project is not None:

            state.execution_context.project_id = (
                request.project
            )

        # ----------------------------------
        # Request Metadata
        # ----------------------------------

        state.execution_context.metadata = dict(
            request.metadata
        )

        return state

    def validate(
        self,
        state: BrainState,
    ) -> dict:
        """
        Validate the Brain registry and current state.
        """

        return self.validator.validate(
            self.registry,
            state,
        )

    def execute(
        self,
        request: Optional[BrainRequest] = None,
    ) -> BrainResponse:
        """
        Execute one complete Brain request.
        """

        state = self.create_state(
            request
        )

        validation = self.validate(
            state
        )

        if not validation["valid"]:

            return BrainResponse(
                success=False,
                state=state,
                error=str(validation),
            )

        result = (
            self.pipeline.execute_with_trace(
                state
            )
        )

        final_state = result["state"]

        trace = result["trace"]

        final_validation = (
            self.validator.validate_state(
                final_state
            )
        )

        if not final_validation["valid"]:

            return BrainResponse(
                success=False,
                state=final_state,
                trace=trace,
                error=str(
                    final_validation
                ),
            )

        return BrainResponse(
            success=True,
            state=final_state,
            trace=trace,
        )

    def get_modules(self):
        """
        Return all registered Intelligence modules.
        """

        return self.registry.get_modules()

    def get_execution_order(self):
        """
        Return the deterministic Intelligence execution order.
        """

        return self.executor.get_execution_order()

    def get_stage_names(self):
        """
        Return the pipeline stage names.
        """

        return self.pipeline.get_stage_names()

    def total_stages(self) -> int:
        """
        Return the number of enabled Brain stages.
        """

        return self.pipeline.total_stages()