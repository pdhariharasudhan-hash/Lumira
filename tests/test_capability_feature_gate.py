import pytest

from app.services.capabilities.capability_router_service import CapabilityRouterService


class FeatureActivation:
    def __init__(self, *, enabled, can_enable=True, blockers=None):
        self.enabled = enabled
        self.can_enable = can_enable
        self.blockers = blockers or []
        self.checked = []

    def status(self, feature):
        self.checked.append(feature)
        return {
            "success": True,
            "feature": feature,
            "metadata": {"enabled": self.enabled},
            "can_enable": self.can_enable,
            "blockers": self.blockers,
        }


class Search:
    def __init__(self):
        self.calls = []

    def search_all(self, query):
        self.calls.append(query)
        return {"success": True, "results": []}


def _router(*, enabled, can_enable=True, blockers=None):
    router = object.__new__(CapabilityRouterService)
    router.features = FeatureActivation(
        enabled=enabled,
        can_enable=can_enable,
        blockers=blockers,
    )
    router.search = Search()
    return router


def test_search_capability_requires_its_feature_to_be_activated():
    router = _router(enabled=False)

    result = router.execute("search", {"query": "project notes"})

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert result["code"] == "feature_not_enabled"
    assert result["feature"] == "unified_search"
    assert router.features.checked == ["unified_search"]
    assert router.search.calls == []


def test_search_capability_requires_dependencies_and_providers_to_be_ready():
    router = _router(
        enabled=True,
        can_enable=False,
        blockers=["required provider is not configured: search"],
    )

    result = router.execute("search", {"query": "project notes"})

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert result["code"] == "feature_not_ready"
    assert result["blockers"] == ["required provider is not configured: search"]
    assert router.search.calls == []


def test_activated_ready_search_capability_executes():
    router = _router(enabled=True)

    result = router.execute("search", {"query": "project notes"})

    assert result["success"] is True
    assert result["results"] == []
    assert router.search.calls == ["project notes"]


def test_search_runtime_gate_follows_persisted_activation_and_dependency_state(tmp_path):
    from app.services.features.feature_activation_service import FeatureActivationService
    from app.services.features.feature_registry_service import FeatureRegistryService

    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    router = _router(enabled=False)
    router.features = FeatureActivationService(registry)

    blocked = router.execute("search", {"query": "project notes"})
    assert blocked["code"] == "feature_not_enabled"
    assert router.search.calls == []

    activated = router.features.activate_with_dependencies("unified_search")
    assert activated["success"] is True

    allowed = router.execute("search", {"query": "project notes"})
    assert allowed["success"] is True
    assert router.search.calls == ["project notes"]


def test_search_runtime_gate_fails_closed_for_stale_enabled_dependency_state(tmp_path):
    from app.services.features.feature_activation_service import FeatureActivationService
    from app.services.features.feature_registry_service import FeatureRegistryService

    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    persisted = registry.get_all()
    persisted["unified_search"]["status"] = "ENABLED"
    persisted["unified_search"]["enabled"] = True
    registry.store.write(persisted)

    router = _router(enabled=True)
    router.features = FeatureActivationService(registry)
    result = router.execute("search", {"query": "project notes"})

    assert result["success"] is False
    assert result["code"] == "feature_not_ready"
    assert any("artifact_manager" in blocker for blocker in result["blockers"])
    assert router.search.calls == []


@pytest.mark.parametrize(
    ("capability", "feature"),
    [
        ("generate_image", "image_generation"),
        ("image_generation", "image_generation"),
        ("web_research", "research"),
        ("technical_research", "research"),
        ("market_research", "research"),
        ("comparison", "research"),
        ("evidence_gathering", "research"),
        ("research_summaries", "research"),
        ("knowledge_extraction", "research"),
    ],
)
@pytest.mark.parametrize(
    ("enabled", "can_enable", "expected_code"),
    [
        (False, True, "feature_not_enabled"),
        (True, False, "feature_not_ready"),
    ],
)
def test_provider_backed_capabilities_share_fail_closed_feature_readiness_gate(
    capability, feature, enabled, can_enable, expected_code
):
    router = _router(
        enabled=enabled,
        can_enable=can_enable,
        blockers=["required provider is not configured"],
    )
    calls = []

    class ImageProvider:
        def generate(self, **kwargs):
            calls.append(("image", kwargs))
            return {"success": True}

    class ResearchProvider:
        def __getattr__(self, name):
            def invoke(request):
                calls.append((name, request))
                return {"success": True}
            return invoke

    router.images = ImageProvider()
    router.research = ResearchProvider()

    result = router.execute(capability, {"prompt": "draw a diagram", "request": "battery storage"})

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert result["code"] == expected_code
    assert result["feature"] == feature
    assert router.features.checked == [feature]
    assert calls == []
