from app.services.brain.brain_state import BrainState
from app.services.constraints.constraint_module import ConstraintModule


def _run_constraint_stage(capability):
    state = BrainState()
    state.context.project_type = "hardware"
    state.context.domain = "engineering"
    if capability is not None:
        state.execution_context.metadata["execute_capability"] = capability
    ConstraintModule().execute(state)
    return state.constraints.missing_information


def test_document_generation_does_not_require_a_programming_stack():
    assert _run_constraint_stage("document_generation") == []


def test_research_and_media_capabilities_do_not_require_a_programming_stack():
    assert _run_constraint_stage("research") == []
    assert _run_constraint_stage("image_generation") == []


def test_code_generation_still_requires_language_and_framework():
    assert _run_constraint_stage("code_generation") == [
        "Programming language not specified.",
        "Framework not specified.",
    ]


def test_legacy_constraint_call_without_capability_keeps_existing_behavior():
    assert _run_constraint_stage(None) == [
        "Programming language not specified.",
        "Framework not specified.",
    ]
