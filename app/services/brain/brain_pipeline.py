"""
brain_pipeline.py

Defines and executes the ordered pipeline for Lumira's
Intelligence Layer.

The pipeline owns orchestration.

It does not contain cognitive logic.
Each Intelligence Module owns its own cognitive operation.

Ownership:
Handoff 12 - Brain Integration
"""

from dataclasses import dataclass
from typing import List

from app.services.brain.brain_executor import (
    BrainExecutor,
)

from app.services.brain.brain_state import (
    BrainState,
)


@dataclass(frozen=True)
class BrainStage:
    """
    Represents a single stage in the Brain pipeline.
    """

    name: str
    order: int
    enabled: bool = True
    required: bool = True


class BrainPipeline:
    """
    Defines and executes the ordered Intelligence Layer.

    The pipeline is deliberately separate from BrainService.

    BrainService:
        Handles the public Brain operation.

    BrainPipeline:
        Defines and executes the cognitive sequence.

    BrainExecutor:
        Executes the registered Intelligence Modules.
    """

    def __init__(
        self,
        executor: BrainExecutor | None = None,
    ) -> None:

        self.executor = (
            executor
            if executor is not None
            else BrainExecutor()
        )

        self._stages: List[BrainStage] = [

            BrainStage(
                name="conversation",
                order=1,
            ),

            BrainStage(
                name="goal",
                order=2,
            ),

            BrainStage(
                name="objective",
                order=3,
            ),

            BrainStage(
                name="context",
                order=4,
            ),

            BrainStage(
                name="constraints",
                order=5,
            ),

            BrainStage(
                name="reasoning",
                order=6,
            ),

            BrainStage(
                name="decision",
                order=7,
            ),

            BrainStage(
                name="planner",
                order=8,
            ),

            BrainStage(
                name="prediction",
                order=9,
            ),

            BrainStage(
                name="verification",
                order=10,
            ),

            BrainStage(
                name="reflection",
                order=11,
            ),

            BrainStage(
                name="learning",
                order=12,
            ),
        ]

    def get_stages(self) -> List[BrainStage]:
        """
        Return all enabled stages in execution order.
        """

        return sorted(
            (
                stage
                for stage in self._stages
                if stage.enabled
            ),
            key=lambda stage: stage.order,
        )

    def get_stage_names(self) -> List[str]:
        """
        Return only enabled stage names.
        """

        return [
            stage.name
            for stage in self.get_stages()
        ]

    def stage_exists(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a stage exists.
        """

        return any(
            stage.name == name
            for stage in self._stages
        )

    def total_stages(self) -> int:
        """
        Return the number of enabled stages.
        """

        return len(
            self.get_stages()
        )

    def execute(
        self,
        state: BrainState,
    ) -> BrainState:
        """
        Execute the complete Intelligence Layer.

        The BrainState is passed through the registered
        Intelligence Modules in deterministic order.
        """

        return self.executor.execute(
            state
        )

    def execute_with_trace(
        self,
        state: BrainState,
        control=None,
    ):
        """
        Execute the Intelligence Layer and return
        both the resulting state and execution trace.
        """

        return self.executor.execute_with_trace(
            state,
            control=control,
        )

    def get_execution_order(self) -> List[str]:
        """
        Return the actual module execution order.
        """

        return self.executor.get_execution_order()