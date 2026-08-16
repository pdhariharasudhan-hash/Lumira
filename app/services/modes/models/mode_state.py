from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ModeState(BaseModel):
    """
    Runtime state for Lumira's active operating mode.

    ModeState is temporary execution state.
    It does not contain permanent memory.

    Ownership:
    Handoff 13.2 - Mode Management
    """

    active_mode: str = "personal"

    previous_mode: Optional[str] = None

    mode_history: List[str] = Field(
        default_factory=list
    )

    manually_selected: bool = False

    activation_reason: str = ""

    confidence: float = 1.0

    last_updated: str = Field(
        default_factory=lambda:
        datetime.utcnow().isoformat()
    )

    def activate(
        self,
        mode_id: str,
        reason: str = "",
        confidence: float = 1.0,
        manual: bool = False,
    ) -> None:
        """
        Activate a new mode and record the transition.
        """

        if self.active_mode != mode_id:

            self.previous_mode = (
                self.active_mode
            )

            self.active_mode = mode_id

            self.mode_history.append(
                mode_id
            )

        elif not self.mode_history:

            self.mode_history.append(
                mode_id
            )

        self.activation_reason = reason

        self.confidence = confidence

        self.manually_selected = manual

        self.last_updated = (
            datetime.utcnow().isoformat()
        )

    def reset(self) -> None:
        """
        Reset the runtime mode state.
        """

        self.active_mode = "personal"

        self.previous_mode = None

        self.mode_history = []

        self.manually_selected = False

        self.activation_reason = ""

        self.confidence = 1.0

        self.last_updated = (
            datetime.utcnow().isoformat()
        )
