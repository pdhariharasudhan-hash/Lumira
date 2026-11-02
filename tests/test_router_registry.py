from app.router_registry import ROUTERS


def test_router_registry_has_unique_router_objects():
    router_ids = [id(router) for router, _ in ROUTERS]
    assert len(router_ids) == len(set(router_ids))


def test_router_registry_is_populated():
    assert len(ROUTERS) > 40
