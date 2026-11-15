import pytest

from app.services.multi_model.model_registry import ModelProfile, MultiModelRegistry


class Worker:
    def generate(self, **kwargs):
        return {"success": True, "content": "ok"}


def setup_function():
    MultiModelRegistry.clear()


def teardown_function():
    MultiModelRegistry.clear()


def test_registry_normalizes_model_id_and_provider_metadata():
    profile = ModelProfile("  local-coder  ", " local ", frozenset({" coding "}))
    MultiModelRegistry.register(profile, Worker())

    registered, provider = MultiModelRegistry.get("local-coder")
    assert registered.model_id == "local-coder"
    assert registered.provider == "local"
    assert registered.capabilities == frozenset({"coding"})
    assert isinstance(provider, Worker)


def test_registry_rejects_accidental_duplicate_and_allows_explicit_replacement():
    first = Worker()
    second = Worker()
    profile = ModelProfile("local-coder", "local", frozenset({"coding"}))
    MultiModelRegistry.register(profile, first)

    with pytest.raises(ValueError, match="already registered"):
        MultiModelRegistry.register(profile, second)

    MultiModelRegistry.register(profile, second, replace_existing=True)
    assert MultiModelRegistry.get("local-coder")[1] is second


@pytest.mark.parametrize(
    "profile",
    [
        ModelProfile("", "local", frozenset({"reply"})),
        ModelProfile("x" * 121, "local", frozenset({"reply"})),
        ModelProfile("model", "", frozenset({"reply"})),
        ModelProfile("model", "local", frozenset()),
        ModelProfile("model", "local", frozenset({" " })),
        ModelProfile("model", "local", frozenset({"reply"}), enabled=1),
        ModelProfile("model", "local", frozenset({"reply"}), priority=True),
    ],
)
def test_registry_rejects_invalid_profiles(profile):
    with pytest.raises(ValueError):
        MultiModelRegistry.register(profile, Worker())


def test_registry_rejects_invalid_profile_type_and_provider_contract():
    with pytest.raises(TypeError, match="ModelProfile"):
        MultiModelRegistry.register(object(), Worker())

    with pytest.raises(ValueError, match="implement generate"):
        MultiModelRegistry.register(
            ModelProfile("model", "local", frozenset({"reply"})),
            object(),
        )


def test_get_unregister_and_eligibility_are_explicit():
    profile = ModelProfile("local", "ollama", frozenset({"reply"}), priority=3)
    worker = Worker()
    MultiModelRegistry.register(profile, worker)

    assert MultiModelRegistry.get("local") == (profile, worker)
    assert MultiModelRegistry.eligible("reply") == [(profile, worker)]
    assert MultiModelRegistry.eligible("coding") == []
    assert MultiModelRegistry.eligible("") == []
    assert MultiModelRegistry.unregister("local") is True
    assert MultiModelRegistry.unregister("local") is False
    assert MultiModelRegistry.get("local") is None


def test_registry_lists_models_in_deterministic_priority_order():
    low = ModelProfile("z-model", "local", frozenset({"reply"}), priority=20)
    high = ModelProfile("a-model", "local", frozenset({"reply"}), priority=1)
    MultiModelRegistry.register(low, Worker())
    MultiModelRegistry.register(high, Worker())

    assert [item.model_id for item in MultiModelRegistry.list()] == [
        "a-model",
        "z-model",
    ]
