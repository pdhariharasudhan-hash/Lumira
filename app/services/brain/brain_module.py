"""
brain_module.py

Defines the base interface for every Brain module.

All Intelligence Layer modules must inherit from BrainModule
and implement the execute() method.

Ownership:
Handoff 11 - Intelligence Layer
"""

from abc import ABC, abstractmethod

from app.services.brain.brain_state import BrainState


class BrainModule(ABC):
    """
    Base interface for all Brain modules.

    Every Intelligence module receives a BrainState,
    updates only its own section,
    and returns the updated BrainState.
    """

    # A stage must explicitly opt in before the executor may retry it.
    retry_safe: bool = False

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable module name.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def order(self) -> int:
        """
        Pipeline execution order.
        """
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        state: BrainState
    ) -> BrainState:
        """
        Execute the module.

        Parameters
        ----------
        state:
            Current BrainState.

        Returns
        -------
        BrainState
            Updated BrainState.
        """
        raise NotImplementedError