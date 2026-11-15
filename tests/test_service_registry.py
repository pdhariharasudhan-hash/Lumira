import pytest

from app.core.service_registry import ServiceRegistry


def test_default_registry_preserves_existing_service_set():
    registry = ServiceRegistry()

    assert registry.list_services() == [
        "planner",
        "builder",
        "execute",
        "code",
        "memory",
        "workspace",
        "dashboard",
    ]
    assert registry.has("planner")
    assert registry.get("missing") is None


def test_registry_supports_injected_services_without_constructing_defaults():
    planner = object()
    custom = object()
    registry = ServiceRegistry(
        {"planner": planner, "custom": custom},
        include_defaults=False,
    )

    assert registry.get("planner") is planner
    assert registry.get("custom") is custom
    assert registry.list_services() == ["planner", "custom"]


def test_register_adds_service_and_returns_registered_instance():
    registry = ServiceRegistry(include_defaults=False)
    service = object()

    assert registry.register("worker", service) is service
    assert registry.get("worker") is service
    assert registry.has("worker")


def test_register_rejects_duplicate_unless_replacement_is_explicit():
    registry = ServiceRegistry({"worker": object()}, include_defaults=False)
    replacement = object()

    with pytest.raises(ValueError, match="already registered"):
        registry.register("worker", object())

    assert registry.register("worker", replacement, replace=True) is replacement
    assert registry.get("worker") is replacement


@pytest.mark.parametrize("name", ["", "   "])
def test_registry_rejects_empty_service_names(name):
    registry = ServiceRegistry(include_defaults=False)

    with pytest.raises(ValueError, match="must not be empty"):
        registry.register(name, object())


def test_registry_rejects_non_string_names_and_none_services():
    registry = ServiceRegistry(include_defaults=False)

    with pytest.raises(TypeError, match="must be a string"):
        registry.register(None, object())

    with pytest.raises(ValueError, match="must not be None"):
        registry.register("worker", None)


def test_unregister_removes_and_returns_service_and_missing_name_raises():
    registry = ServiceRegistry({"worker": object()}, include_defaults=False)
    service = registry.unregister("worker")

    assert service is not None
    assert registry.has("worker") is False
    with pytest.raises(KeyError):
        registry.unregister("worker")


def test_injected_services_cannot_silently_shadow_default_services():
    with pytest.raises(ValueError, match="conflict with default"):
        ServiceRegistry({"planner": object()})


def test_registry_concurrent_registration_keeps_all_services():
    from concurrent.futures import ThreadPoolExecutor

    registry = ServiceRegistry(include_defaults=False)
    services = {f"worker-{index}": object() for index in range(32)}

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda item: registry.register(item[0], item[1]),
                services.items(),
            )
        )

    assert len(results) == 32
    assert set(registry.list_services()) == set(services)
    assert len(registry.list_services()) == 32
    assert all(registry.get(name) is service for name, service in services.items())
