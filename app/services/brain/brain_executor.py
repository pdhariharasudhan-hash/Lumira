"""
brain_executor.py

Executes Lumira's Intelligence Layer modules sequentially.

The executor receives a BrainState and passes it through every
registered Intelligence module in deterministic order.

Ownership:
Handoff 12 - Brain Integration
"""

from typing import Any, Dict, List

from app.services.brain.brain_registry import (
    BrainRegistry,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.brain.recovery import (
    RecoveryController,
    RecoveryPolicy,
    RecoveryState,
)


class BrainExecutor:
    """
    Executes registered Brain modules sequentially.
    """

    def __init__(
        self,
        registry: BrainRegistry | None = None,
    ) -> None:

        self.registry = (
            registry
            if registry is not None
            else BrainRegistry()
        )

        self.last_recovery_state = None

    def get_recovery_state(self):
        """
        Return the recovery state produced by the most recent
        execute() or resume() operation.

        None means no execution has occurred yet.
        """

        return self.last_recovery_state

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute every registered Intelligence module.

        Failures are captured by the native recovery subsystem.
        Recovery retries the failed stage deterministically.

        The recovery state is owned by this execution and is
        persisted to last_recovery_state whether execution
        succeeds or fails.
        """

        modules = self.registry.get_modules()

        ordered_modules = sorted(
            modules,
            key=lambda module: module.order,
        )

        recovery_state = RecoveryState()

        self.last_recovery_state = recovery_state

        controller = RecoveryController(
            RecoveryPolicy(
                max_retries=2,
                allow_recovery=True,
            )
        )

        for module in ordered_modules:

            module_name = getattr(
                module,
                "name",
                module.__class__.__name__,
            )

            order = getattr(
                module,
                "order",
                None,
            )

            while True:

                try:

                    result = module.execute(
                        state
                    )

                    if result is not None:
                        state = result

                    if recovery_state.failures:

                        latest = recovery_state.failures[-1]

                        if (
                            latest.stage == module_name
                            and latest.order == order
                            and not latest.aborted
                            and not latest.recovered
                        ):
                            controller.recover(
                                recovery_state
                            )

                            controller.reset_retry(
                        recovery_state
                    )

                    break

                except Exception as exc:

                    recovery_state.record_failure(
                        stage=module_name,
                        order=order,
                        error=str(exc),
                    )

                    if controller.retry(
                        recovery_state
                    ):
                        continue

                    controller.abort(
                        recovery_state
                    )

                    self.last_recovery_state = (
                        recovery_state
                    )

                    raise

        self.last_recovery_state = recovery_state

        return state

    def execute_with_trace(
        self,
        state: BrainState,
    ) -> Dict[str, Any]:
        """
        Execute the Brain pipeline with deterministic recovery
        and recovery-aware diagnostic tracing.

        The trace is temporary diagnostic information and is
        not permanent memory.
        """

        trace: List[Dict[str, Any]] = []

        modules = self.registry.get_modules()

        ordered_modules = sorted(
            modules,
            key=lambda module: module.order,
        )

        recovery_state = RecoveryState()

        self.last_recovery_state = recovery_state

        controller = RecoveryController(
            RecoveryPolicy(
                max_retries=2,
                allow_recovery=True,
            )
        )

        for module in ordered_modules:

            module_name = getattr(
                module,
                "name",
                module.__class__.__name__,
            )

            module_order = getattr(
                module,
                "order",
                None,
            )

            attempt = 0

            while True:

                attempt += 1
                state.current_stage = module_name
                state.status = "running"

                trace_entry = {
                    "module": module_name,
                    "order": module_order,
                    "status": "started",
                    "attempt": attempt,
                    "recovery": False,
                    "error": None,
                }

                trace.append(trace_entry)

                try:

                    result = module.execute(
                        state
                    )

                    if result is not None:
                        state = result

                    trace_entry["status"] = "completed"
                    state.last_completed_stage = module_name

                    if recovery_state.failures:

                        latest = (
                            recovery_state.failures[-1]
                        )

                        if (
                            latest.stage == module_name
                            and latest.order == module_order
                            and not latest.aborted
                        ):
                            controller.recover(
                                recovery_state
                            )

                            trace_entry[
                                "recovery"
                            ] = True

                            trace_entry[
                                "recovery_status"
                            ] = "recovered"

                            controller.reset_retry(
                        recovery_state
                    )

                    break

                except Exception as exc:

                    trace_entry["status"] = "failed"
                    trace_entry["error"] = str(exc)
                    trace_entry["recovery"] = True
                    trace_entry[
                        "recovery_status"
                    ] = "failure"

                    recovery_state.record_failure(
                        stage=module_name,
                        order=module_order,
                        error=str(exc),
                    )

                    if controller.retry(
                        recovery_state
                    ):
                        trace_entry[
                            "recovery_status"
                        ] = "retrying"

                        continue

                    controller.abort(
                        recovery_state
                    )
                    state.status = "failed"

                    trace_entry[
                        "recovery_status"
                    ] = "aborted"

                    self.last_recovery_state = (
                        recovery_state
                    )

                    raise

        self.last_recovery_state = (
            recovery_state
        )
        state.status = "completed"
        state.current_stage = ""

        return {
            "state": state,
            "trace": trace,
        }

    def get_execution_order(self) -> List[str]:
        """
        Return the current execution order.
        """

        modules = self.registry.get_modules()

        ordered_modules = sorted(
            modules,
            key=lambda module: module.order,
        )

        return [
            getattr(
                module,
                "name",
                module.__class__.__name__,
            )
            for module in ordered_modules
        ]


    def resume(self, state, start_order):
        """
        Resume deterministic execution from the specified stage order.

        Stages before start_order are not executed.

        Recovery is natively integrated so a failed resumed stage
        receives the same bounded retry behavior as normal execution.
        """

        execution_order = self.get_execution_order()

        if not isinstance(start_order, int):
            raise TypeError(
                "start_order must be an integer"
            )

        if start_order < 1 or start_order > len(execution_order):
            raise ValueError(
                f"start_order must be between 1 and {len(execution_order)}"
            )

        recovery_state = RecoveryState()

        controller = RecoveryController(
            RecoveryPolicy(
                max_retries=2,
                allow_recovery=True,
            )
        )

        for order in range(
            start_order,
            len(execution_order) + 1,
        ):

            module_name = execution_order[
                order - 1
            ]

            modules = self.registry.get_modules()

            module = next(
                (
                    candidate
                    for candidate in modules
                    if getattr(
                        candidate,
                        "name",
                        None,
                    ) == module_name
                    or candidate.__class__.__name__.lower().replace(
                        "module",
                        "",
                    ) == module_name.lower()
                ),
                None,
            )

            if module is None:
                raise RuntimeError(
                    f"Brain module not found: {module_name}"
                )

            while True:

                try:

                    result = module.execute(
                        state
                    )

                    if result is not None:
                        state = result

                    break

                except Exception as exc:

                    recovery_state.record_failure(
                        stage=module_name,
                        order=order,
                        error=str(exc),
                    )

                    if controller.retry(
                        recovery_state
                    ):
                        continue

                    controller.abort(
                        recovery_state
                    )

                    self.last_recovery_state = (
                        recovery_state
                    )

                    raise

            if recovery_state.failures:

                latest = recovery_state.failures[-1]

                if (
                    latest.stage == module_name
                    and latest.order == order
                ):
                    controller.recover(
                        recovery_state
                    )

                    controller.reset_retry(
                        recovery_state
                    )

        self.last_recovery_state = recovery_state

        return state
