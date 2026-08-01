"""
brain_pipeline.py

Defines the execution pipeline for Lumira's Intelligence Layer.

The pipeline is intentionally separated from BrainService so that
new intelligence stages can be added, removed, reordered, or
disabled without modifying the orchestration logic.

Ownership:
Handoff 11 - Intelligence Layer
"""

from dataclasses import dataclass
from typing import List


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
    Defines the ordered execution stages for the
    Lumira Intelligence Layer.
    """

    def __init__(self) -> None:

        self._stages: List[BrainStage] = [

            BrainStage(
                name="conversation",
                order=1
            ),

            BrainStage(
                name="goal",
                order=2
            ),

            BrainStage(
                name="objective",
                order=3
            ),

            BrainStage(
                name="context",
                order=4
            ),

            BrainStage(
                name="constraints",
                order=5
            ),

            BrainStage(
                name="reasoning",
                order=6
            ),

            BrainStage(
                name="decision",
                order=7
            ),

            BrainStage(
                name="planner",
                order=8
            ),

            BrainStage(
                name="prediction",
                order=9
            ),

            BrainStage(
                name="verification",
                order=10
            ),

            BrainStage(
                name="reflection",
                order=11
            ),

            BrainStage(
                name="learning",
                order=12
            )

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
            key=lambda stage: stage.order
        )

    def get_stage_names(self) -> List[str]:
        """
        Return only stage names.
        """

        return [
            stage.name
            for stage in self.get_stages()
        ]

    def stage_exists(
        self,
        name: str
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