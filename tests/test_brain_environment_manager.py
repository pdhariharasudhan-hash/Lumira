import pytest

from app.services.brain.brain_config import BrainConfig
from app.services.brain.brain_environment_manager import (
    BrainEnvironmentError,
    BrainEnvironmentManager,
)


def test_environment_defaults_to_development():
    manager = BrainEnvironmentManager(BrainConfig({}))
    assert manager.resolve() == "development"


def test_environment_can_be_selected_from_configuration():
    manager = BrainEnvironmentManager(BrainConfig({"LUMIRA_ENVIRONMENT": "prod"}))
    assert manager.resolve() == "production"


@pytest.mark.parametrize("alias,expected", [
    ("dev", "development"), ("test", "testing"),
    ("stage", "staging"), ("prod", "production"),
])
def test_environment_aliases_are_normalized(alias, expected):
    assert BrainEnvironmentManager.normalize(alias) == expected


def test_explicit_request_environment_overrides_configuration():
    manager = BrainEnvironmentManager(BrainConfig({"LUMIRA_ENVIRONMENT": "production"}))
    assert manager.resolve("testing") == "testing"


@pytest.mark.parametrize("invalid", ["", "unknown", "offline", None])
def test_unsupported_environment_is_rejected(invalid):
    if invalid is None:
        manager = BrainEnvironmentManager(BrainConfig({"LUMIRA_ENVIRONMENT": "offline"}))
        with pytest.raises(BrainEnvironmentError):
            manager.resolve()
    else:
        with pytest.raises(BrainEnvironmentError):
            BrainEnvironmentManager.normalize(invalid)


def test_contexts_are_independent_and_request_scoped():
    manager = BrainEnvironmentManager(BrainConfig({}))
    first = manager.create_context(environment="test", session_id="s1", metadata={"x": 1})
    second = manager.create_context(environment="prod", session_id="s2")
    assert first.environment == "testing"
    assert second.environment == "production"
    assert first.execution_id != second.execution_id
    first.metadata["x"] = 2
    assert second.metadata == {}


def test_invalid_context_fields_are_rejected():
    manager = BrainEnvironmentManager(BrainConfig({}))
    with pytest.raises(BrainEnvironmentError, match="workspace"):
        manager.create_context(workspace=" ")
    with pytest.raises(BrainEnvironmentError, match="metadata"):
        manager.create_context(metadata=[])


def test_brain_service_builds_request_context_through_environment_manager():
    from app.services.brain.brain_request import BrainRequest
    from app.services.brain.brain_service import BrainService

    class IntentStub:
        @staticmethod
        def classify(message):
            return {"intent": "test"}

    service = BrainService.__new__(BrainService)
    service.environment_manager = BrainEnvironmentManager(BrainConfig({}))
    service.intent_classifier = IntentStub()
    state = service.create_state(BrainRequest(
        message="hello",
        session_id="session-1",
        project="project-1",
        environment="test",
        workspace="workspace-1",
        metadata={"trace": "safe"},
    ))
    assert state.execution_context.environment == "testing"
    assert state.execution_context.session_id == "session-1"
    assert state.execution_context.project_id == "project-1"
    assert state.execution_context.workspace == "workspace-1"
    assert state.execution_context.metadata == {"trace": "safe"}


def test_brain_service_rejects_unknown_environment_before_execution():
    from app.services.brain.brain_request import BrainRequest
    from app.services.brain.brain_service import BrainService

    class IntentStub:
        @staticmethod
        def classify(message):
            return {"intent": "test"}

    service = BrainService.__new__(BrainService)
    service.environment_manager = BrainEnvironmentManager(BrainConfig({}))
    service.intent_classifier = IntentStub()
    with pytest.raises(BrainEnvironmentError):
        service.create_state(BrainRequest(message="hello", environment="unknown"))


def test_brain_service_uses_configured_environment_when_request_omits_it():
    from app.services.brain.brain_request import BrainRequest
    from app.services.brain.brain_service import BrainService

    class IntentStub:
        @staticmethod
        def classify(message):
            return {"intent": "test"}

    service = BrainService.__new__(BrainService)
    service.environment_manager = BrainEnvironmentManager(
        BrainConfig({"LUMIRA_ENVIRONMENT": "staging"})
    )
    service.intent_classifier = IntentStub()
    state = service.create_state(BrainRequest(message="hello"))
    assert state.execution_context.environment == "staging"
