"""
brain_service.py

Main orchestrator for Lumira's Intelligence Layer.

BrainService coordinates execution of all registered
Brain modules.

It does NOT contain intelligence itself.

Ownership:
Handoff 11 - Intelligence Layer
"""

from typing import List

from app.services.brain.brain_module import BrainModule
from app.services.brain.brain_pipeline import BrainPipeline
from app.services.brain.brain_state import BrainState


class BrainService:
    """
    Main entry point for Lumira's Brain.

    Creates a fresh BrainState,
    executes every registered BrainModule
    in pipeline order,
    and returns the completed state.
    """

    def __init__(self) -> None:

        self.pipeline = BrainPipeline()

        self.modules: List[BrainModule] = []

    def register(
        self,
        module: BrainModule
    ) -> None:
        """
        Register a Brain module.
        """

        self.modules.append(module)

        self.modules.sort(
            key=lambda m: m.order
        )

    def clear_modules(self) -> None:
        """
        Remove all registered modules.
        """

        self.modules.clear()

    def get_modules(self) -> List[BrainModule]:
        """
        Return registered modules.
        """

        return list(self.modules)

    def execute(self) -> BrainState:
        """
        Execute the Intelligence Layer.
        """

        state = BrainState()

        enabled = {
            stage.name
            for stage in self.pipeline.get_stages()
        }

        for module in self.modules:

            if module.name not in enabled:
                continue

            state = module.execute(state)

        return state
        