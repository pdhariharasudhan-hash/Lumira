"""
brain_context.py

Defines the execution context for Lumira's Brain.

BrainContext contains execution-level metadata only.

It does NOT contain intelligence states and does NOT duplicate
BrainState.

Ownership:
Lumira Brain Architecture
"""

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from pydantic import BaseModel, Field


class BrainContext(BaseModel):
    """
    Execution-level context for a single Brain run.

    BrainContext describes WHERE and UNDER WHAT CONDITIONS
    the Brain is executing.

    Cognitive state belongs exclusively to BrainState.
    """

    execution_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    request_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    session_id: str = ""

    project_id: str = ""

    environment: str = "development"

    workspace: str = "default"

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )

    created_at: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    )

    last_updated: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    )

    def update(
        self,
        **values: Any,
    ) -> None:
        """
        Update execution context values.
        """

        for key, value in values.items():

            if hasattr(self, key):
                setattr(
                    self,
                    key,
                    value,
                )

        self.last_updated = (
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        )

    def reset(self) -> None:
        """
        Reset the execution context.
        """

        self.execution_id = str(uuid4())

        self.request_id = str(uuid4())

        self.session_id = ""

        self.project_id = ""

        self.environment = "development"

        self.workspace = "default"

        self.metadata.clear()

        timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        self.created_at = timestamp

        self.last_updated = timestamp

    def to_dict(self) -> Dict[str, Any]:
        """
        Export the BrainContext as a dictionary.
        """

        return self.model_dump()