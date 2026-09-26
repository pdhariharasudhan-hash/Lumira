from typing import List

from app.services.modes.mode_registry_service import (
    ModeRegistryService,
)
from app.services.modes.models.mode_state import (
    ModeState,
)


class ModeCapabilityService:
    """
    Deterministic bridge between the active ModeState and
    the capability policy defined by ModeDefinition.

    This service does not execute capabilities.

    It only answers:
    - which capabilities are prioritized by the active mode
    - which capabilities are restricted by the active mode
    - whether a capability is allowed
    - how strongly a capability is prioritized

    Mode state is request-local and is never stored globally.
    """

    def __init__(
        self,
        registry: ModeRegistryService = None,
    ) -> None:

        self.registry = (
            registry
            if registry is not None
            else ModeRegistryService()
        )

    # ----------------------------------
    # MODE RESOLUTION
    # ----------------------------------

    def get_mode_definition(
        self,
        mode_state: ModeState,
    ):
        """
        Resolve the active mode definition.

        Raises the registry's canonical error for an
        unknown mode instead of silently guessing.
        """

        if mode_state is None:
            raise ValueError(
                "mode_state is required"
            )

        mode_id = mode_state.active_mode

        return self.registry.require(mode_id)

    # ----------------------------------
    # PRIORITY CAPABILITIES
    # ----------------------------------

    def get_priority_capabilities(
        self,
        mode_state: ModeState,
    ) -> List[str]:

        mode = self.get_mode_definition(
            mode_state
        )

        return list(
            mode.priority_capabilities
        )

    # ----------------------------------
    # RESTRICTED CAPABILITIES
    # ----------------------------------

    def get_restricted_capabilities(
        self,
        mode_state: ModeState,
    ) -> List[str]:

        mode = self.get_mode_definition(
            mode_state
        )

        return list(
            mode.restricted_capabilities
        )

    # ----------------------------------
    # CAPABILITY STATUS
    # ----------------------------------

    def is_priority(
        self,
        mode_state: ModeState,
        capability: str,
    ) -> bool:

        capability = self._normalize(
            capability
        )

        return capability in {
            self._normalize(item)
            for item in self.get_priority_capabilities(
                mode_state
            )
        }

    def is_restricted(
        self,
        mode_state: ModeState,
        capability: str,
    ) -> bool:

        capability = self._normalize(
            capability
        )

        return capability in {
            self._normalize(item)
            for item in self.get_restricted_capabilities(
                mode_state
            )
        }

    def is_allowed(
        self,
        mode_state: ModeState,
        capability: str,
    ) -> bool:

        return not self.is_restricted(
            mode_state,
            capability,
        )

    # ----------------------------------
    # DETERMINISTIC PRIORITY
    # ----------------------------------

    def get_priority(
        self,
        mode_state: ModeState,
        capability: str,
    ) -> int:

        capability = self._normalize(
            capability
        )

        priorities = [
            self._normalize(item)
            for item in self.get_priority_capabilities(
                mode_state
            )
        ]

        if capability in priorities:
            return priorities.index(
                capability
            ) + 1

        return 0

    # ----------------------------------
    # ROUTING DECISION
    # ----------------------------------

    def resolve(
        self,
        mode_state: ModeState,
        capability: str,
    ) -> dict:

        normalized = self._normalize(
            capability
        )

        return {
            "mode": mode_state.active_mode,
            "capability": normalized,
            "allowed": self.is_allowed(
                mode_state,
                normalized,
            ),
            "priority": self.get_priority(
                mode_state,
                normalized,
            ),
            "restricted": self.is_restricted(
                mode_state,
                normalized,
            ),
            "is_priority": self.is_priority(
                mode_state,
                normalized,
            ),
        }

    # ----------------------------------
    # NORMALIZATION
    # ----------------------------------

    @staticmethod
    def _normalize(
        capability: str,
    ) -> str:

        if not isinstance(
            capability,
            str,
        ):
            raise TypeError(
                "capability must be a string"
            )

        return capability.strip().lower()

