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

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute every registered Intelligence module.

        The same BrainState instance is passed through the
        complete cognitive pipeline.
        """

        modules = self.registry.get_modules()

        ordered_modules = sorted(
            modules,
            key=lambda module: module.order,
        )

        for module in ordered_modules:

            result = module.execute(
                state
            )

            if result is not None:
                state = result

        return state

    def execute_with_trace(
        self,
        state: BrainState,
    ) -> Dict[str, Any]:
        """
        Execute the Brain pipeline while recording a simple
        execution trace.

        The trace is temporary diagnostic information and is
        not permanent memory.
        """

        trace: List[Dict[str, Any]] = []

        modules = self.registry.get_modules()

        ordered_modules = sorted(
            modules,
            key=lambda module: module.order,
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

            trace.append(
                {
                    "module": module_name,
                    "order": module_order,
                    "status": "started",
                }
            )

            result = module.execute(
                state
            )

            if result is not None:
                state = result

            trace[-1]["status"] = "completed"

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