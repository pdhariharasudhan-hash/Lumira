"""
mode_manager_service.py

Manages Lumira's active operating mode.

The manager:
- validates modes
- activates modes
- switches modes
- tracks mode transitions
- supports manual mode selection

It does NOT:
- detect user intent
- execute capabilities
- modify BrainState
- implement mode-specific capabilities
- create separate AI systems

All modes continue to use the same Lumira Core.

Ownership:
Handoff 13.2 - Mode Management
"""

from app.services.modes.mode_registry_service import (
    ModeRegistryService,
)

from app.services.modes.models.mode_state import (
    ModeState,
)


class ModeManagerService:
    """
    Central manager for Lumira's active operating mode.
    """

    def __init__(
        self,
        registry: ModeRegistryService | None = None,
    ) -> None:

        self.registry = (
            registry
            if registry is not None
            else ModeRegistryService()
        )

        self.state = ModeState()

        self.state.activate(
            mode_id="personal",
            reason="default_mode",
            confidence=1.0,
            manual=False,
        )

    # ----------------------------------
    # Current Mode
    # ----------------------------------

    def get_active_mode(self):

        return self.registry.require(
            self.state.active_mode
        )

    def get_active_mode_id(
        self,
    ) -> str:

        return self.state.active_mode

    # ----------------------------------
    # Activation
    # ----------------------------------

    def activate(
        self,
        mode_id: str,
        reason: str = "",
        confidence: float = 1.0,
        manual: bool = False,
    ):

        mode = self.registry.require(
            mode_id
        )

        self.state.activate(
            mode_id=mode.id,
            reason=reason,
            confidence=confidence,
            manual=manual,
        )

        return mode

    # ----------------------------------
    # Manual Selection
    # ----------------------------------

    def select(
        self,
        mode_id: str,
    ):

        return self.activate(
            mode_id=mode_id,
            reason="manual_selection",
            confidence=1.0,
            manual=True,
        )

    # ----------------------------------
    # Switching
    # ----------------------------------

    def switch(
        self,
        mode_id: str,
        reason: str = "",
    ):

        return self.activate(
            mode_id=mode_id,
            reason=reason,
            confidence=1.0,
            manual=False,
        )

    # ----------------------------------
    # State
    # ----------------------------------

    def get_state(
        self,
    ) -> ModeState:

        return self.state

    def get_history(self):

        return list(
            self.state.mode_history
        )

    # ----------------------------------
    # Validation
    # ----------------------------------

    def exists(
        self,
        mode_id: str,
    ) -> bool:

        return self.registry.exists(
            mode_id
        )

    def require(
        self,
        mode_id: str,
    ):

        return self.registry.require(
            mode_id
        )

    # ----------------------------------
    # Reset
    # ----------------------------------

    def reset(self) -> None:

        self.state.reset()
