"""
brain_validator.py

Validates Brain execution state and registry configuration.

The validator performs structural validation only.

It does not perform cognitive reasoning.

Ownership:
Handoff 12 - Brain Integration
"""

from typing import Any, Dict

from app.services.brain.brain_registry import (
    BrainRegistry,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.features.core_feature_contract import (
    CoreFeatureContract,
)


class BrainValidator:
    """
    Validates the structural integrity of the Brain pipeline.
    """

    def validate_registry(
        self,
        registry: BrainRegistry,
    ) -> Dict[str, Any]:
        """
        Validate the Brain registry.
        """

        modules = registry.get_modules()

        if not modules:
            return {
                "valid": False,
                "error": "Brain registry contains no modules.",
            }

        orders = [
            module.order
            for module in modules
        ]

        if len(orders) != len(set(orders)):
            return {
                "valid": False,
                "error": (
                    "Brain modules contain duplicate "
                    "execution orders."
                ),
            }

        sorted_orders = sorted(orders)

        expected_orders = list(
            range(
                1,
                len(orders) + 1,
            )
        )

        if sorted_orders != expected_orders:
            return {
                "valid": False,
                "error": (
                    "Brain module execution orders are not "
                    "sequential."
                ),
            }

        return {
            "valid": True,
            "module_count": len(modules),
            "module_names": [
                getattr(
                    module,
                    "name",
                    module.__class__.__name__,
                )
                for module in modules
            ],
            "execution_orders": sorted_orders,
        }

    def validate_state(
        self,
        state: BrainState,
    ) -> Dict[str, Any]:
        """
        Validate that a BrainState is structurally valid.
        """

        if not isinstance(
            state,
            BrainState,
        ):
            return {
                "valid": False,
                "error": "Invalid BrainState instance.",
            }

        contract = CoreFeatureContract()
        contract_result = contract.validate_state(
            state.model_dump()
        )
        if not contract_result["valid"]:
            return {
                "valid": False,
                "state_type": state.__class__.__name__,
                "execution_id": state.execution_context.execution_id,
                "contract": contract_result,
            }

        return {
            "valid": True,
            "state_type": state.__class__.__name__,
            "execution_id": state.execution_context.execution_id,
            "contract": contract_result,
        }

    def validate(
        self,
        registry: BrainRegistry,
        state: BrainState,
    ) -> Dict[str, Any]:
        """
        Validate both registry and BrainState.
        """

        registry_result = self.validate_registry(
            registry
        )

        if not registry_result["valid"]:
            return {
                "valid": False,
                "registry": registry_result,
                "state": None,
            }

        state_result = self.validate_state(
            state
        )

        if not state_result["valid"]:
            return {
                "valid": False,
                "registry": registry_result,
                "state": state_result,
            }

        return {
            "valid": True,
            "registry": registry_result,
            "state": state_result,
        }