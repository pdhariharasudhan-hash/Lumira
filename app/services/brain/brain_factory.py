"""
brain_factory.py

Creates and assembles Brain integration components.

Ownership:
Handoff 12 - Brain Integration
"""

from app.services.brain.brain_executor import (
    BrainExecutor,
)

from app.services.brain.brain_registry import (
    BrainRegistry,
)

from app.services.brain.brain_validator import (
    BrainValidator,
)


class BrainFactory:
    """
    Factory responsible for creating the core Brain components.
    """

    @staticmethod
    def create_registry() -> BrainRegistry:
        """
        Create a BrainRegistry.
        """

        return BrainRegistry()

    @staticmethod
    def create_executor(
        registry: BrainRegistry | None = None,
    ) -> BrainExecutor:
        """
        Create a BrainExecutor.

        If a registry is supplied, the executor uses it.
        Otherwise a new registry is created.
        """

        if registry is None:
            registry = BrainFactory.create_registry()

        return BrainExecutor(
            registry=registry
        )

    @staticmethod
    def create_validator() -> BrainValidator:
        """
        Create a BrainValidator.
        """

        return BrainValidator()

    @staticmethod
    def create_brain_components():
        """
        Create the complete set of core Brain components.
        """

        registry = BrainFactory.create_registry()

        executor = BrainFactory.create_executor(
            registry=registry
        )

        validator = BrainFactory.create_validator()

        return {
            "registry": registry,
            "executor": executor,
            "validator": validator,
        }