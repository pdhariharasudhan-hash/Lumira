import pytest

from app.services.brain.brain_module import BrainModule
from app.services.brain.brain_registry import BrainRegistry
from app.services.brain.brain_state import BrainState


class StubModule(BrainModule):
    def __init__(self, name: str, order: int):
        self._name = name
        self._order = order

    @property
    def name(self):
        return self._name

    @property
    def order(self):
        return self._order

    def execute(self, state: BrainState) -> BrainState:
        return state


def test_default_registry_preserves_twelve_stage_order_and_legacy_api():
    registry = BrainRegistry()
    assert registry.count() == 12
    assert [m.name for m in registry.get_modules()] == [
        "conversation", "goal", "objective", "context", "constraints", "reasoning",
        "decision", "planner", "prediction", "verification", "reflection", "learning",
    ]
    assert registry.get_module_names()[0] == "ConversationModule"


def test_custom_registry_is_injected_without_default_modules():
    custom = [StubModule("custom", 1)]
    registry = BrainRegistry(custom)
    assert registry.get_modules() == custom
    assert registry.get_module("custom") is custom[0]


def test_register_sorts_by_order_and_returns_registered_module():
    registry = BrainRegistry([StubModule("later", 2)])
    first = StubModule("first", 1)
    assert registry.register_module(first) is first
    assert [m.name for m in registry.get_modules()] == ["first", "later"]


def test_duplicate_name_requires_explicit_replacement():
    registry = BrainRegistry([StubModule("custom", 1)])
    replacement = StubModule("custom", 1)
    with pytest.raises(ValueError, match="already registered"):
        registry.register_module(replacement)
    assert registry.register_module(replacement, replace=True) is replacement
    assert registry.get_module("custom") is replacement


def test_duplicate_order_is_rejected():
    registry = BrainRegistry([StubModule("one", 1)])
    with pytest.raises(ValueError, match="already used"):
        registry.register_module(StubModule("two", 1))


@pytest.mark.parametrize("module", [None, object()])
def test_invalid_module_type_is_rejected(module):
    with pytest.raises(TypeError, match="BrainModule"):
        BrainRegistry([module])


def test_invalid_module_identity_is_rejected():
    with pytest.raises(ValueError, match="name"):
        BrainRegistry([StubModule(" ", 1)])
    with pytest.raises(ValueError, match="positive integer"):
        BrainRegistry([StubModule("bad-order", 0)])


def test_registry_enforces_executor_module_limit():
    modules = [StubModule(f"m{i}", i + 1) for i in range(12)]
    registry = BrainRegistry(modules)
    with pytest.raises(ValueError, match="cannot exceed 12"):
        registry.register_module(StubModule("overflow", 13))


def test_unregister_returns_module_and_missing_returns_none():
    module = StubModule("custom", 1)
    registry = BrainRegistry([module])
    assert registry.unregister_module("custom") is module
    assert registry.unregister_module("missing") is None
    assert registry.count() == 0


def test_get_modules_returns_a_snapshot():
    registry = BrainRegistry([StubModule("custom", 1)])
    snapshot = registry.get_modules()
    snapshot.clear()
    assert registry.count() == 1
