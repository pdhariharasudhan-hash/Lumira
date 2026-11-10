from typing import Any


class PipelineGuard:
    """Central deterministic stop rules for intelligence pipeline stages."""

    @staticmethod
    def verification_result(state: Any) -> dict:
        verification = getattr(state, "verification", None)
        return {
            "ready_for_execution": bool(
                getattr(verification, "ready_for_execution", False)
            ),
            "passed_checks": list(
                getattr(verification, "passed_checks", [])
            ),
            "failed_checks": list(
                getattr(verification, "failed_checks", [])
            ),
            "warnings": list(getattr(verification, "warnings", [])),
        }

    @classmethod
    def should_stop(cls, module_name: str, state: Any) -> bool:
        if str(module_name).lower() not in {
            "verification",
            "verificationmodule",
        }:
            return False
        state.verification_result = cls.verification_result(state)
        # A normal Brain request may legitimately produce a plan that needs
        # clarification; reflection and learning should still complete. Only
        # an explicitly requested side-effecting capability is stopped here.
        metadata = getattr(
            getattr(state, "execution_context", None),
            "metadata",
            None,
        )
        if not isinstance(metadata, dict):
            return not state.verification_result["ready_for_execution"]
        return (
            metadata.get("execute_capability") is not None
            and not state.verification_result["ready_for_execution"]
        )
