"""
brain_service.py

Main entry point for Lumira's Intelligence Layer.

BrainService coordinates the complete Brain execution flow.

It does not contain cognitive intelligence itself.

Flow:

BrainRequest
    ?
BrainState
    ?
Command History
    ?
BrainValidator
    ?
BrainPipeline
    ?
BrainExecutor
    ?
Pipeline History
    ?
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

from app.services.history.command_history_service import (
    CommandHistoryService,
)

from app.services.history.pipeline_history_service import (
    PipelineHistoryService,
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

        self.command_history = (
            CommandHistoryService()
        )

        self.pipeline_history = (
            PipelineHistoryService()
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

        Request-level information is propagated into
        the BrainState and its execution context.
        """

        state = BrainState()

        if request is None:
            return state

        state.user_input = request.message

        state.execution_context.update(
            session_id=request.session_id,
            project_id=request.project or "",
            environment=request.environment,
            workspace=request.workspace,
            metadata=dict(request.metadata),
        )

        return state

    def _record_command(
        self,
        state: BrainState,
    ) -> None:
        """
        Record the incoming command using the current
        BrainState execution identity.
        """

        context = state.execution_context

        self.command_history.record(
            request_id=context.request_id,
            execution_id=context.execution_id,
            session_id=context.session_id,
            project_id=context.project_id,
            message=state.user_input,
            environment=context.environment,
            workspace=context.workspace,
            metadata=dict(context.metadata),
        )

    def _record_pipeline(
        self,
        state: BrainState,
        success: bool,
        trace: list,
        error: Optional[str] = None,
    ) -> None:
        """
        Record the completed or failed pipeline using
        the SAME BrainState execution identity.
        """

        context = state.execution_context

        self.pipeline_history.record(
            execution_id=context.execution_id,
            request_id=context.request_id,
            session_id=context.session_id,
            project_id=context.project_id,
            user_input=state.user_input,
            success=success,
            trace=trace,
            error=error,
        )

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

        One request creates exactly one BrainState.
        That same state owns the execution identity used
        by command history and pipeline history.
        """

        state = self.create_state(
            request
        )

        # ----------------------------------
        # Record incoming command
        # ----------------------------------

        self._record_command(
            state
        )

        # ----------------------------------
        # Initial validation
        # ----------------------------------

        validation = self.validate(
            state
        )

        if not validation["valid"]:

            error = str(validation)

            self._record_pipeline(
                state=state,
                success=False,
                trace=[],
                error=error,
            )

            return BrainResponse(
                success=False,
                state=state,
                error=error,
            )

        # ----------------------------------
        # Brain Pipeline
        # ----------------------------------

        trace = []

        try:

            result = (
                self.pipeline.execute_with_trace(
                    state
                )
            )

            final_state = result["state"]

            trace = result["trace"]

        except Exception as exc:

            error = (
                f"{type(exc).__name__}: {exc}"
            )

            self._record_pipeline(
                state=state,
                success=False,
                trace=trace,
                error=error,
            )

            return BrainResponse(
                success=False,
                state=state,
                trace=trace,
                error=error,
            )

        # ----------------------------------
        # Final validation
        # ----------------------------------

        final_validation = (
            self.validator.validate_state(
                final_state
            )
        )

        if not final_validation["valid"]:

            error = str(
                final_validation
            )

            self._record_pipeline(
                state=final_state,
                success=False,
                trace=trace,
                error=error,
            )

            return BrainResponse(
                success=False,
                state=final_state,
                trace=trace,
                error=error,
            )

        # ----------------------------------
        # Successful pipeline history
        # ----------------------------------

        self._record_pipeline(
            state=final_state,
            success=True,
            trace=trace,
            error=None,
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
