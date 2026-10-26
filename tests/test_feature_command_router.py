from app.services.features.feature_command_router import FeatureCommandRouter


class FakeIdentity:
    def __init__(self, parsed):
        self.parsed = parsed

    def parse(self, text):
        return self.parsed


class FakeActivation:
    def __init__(self, result):
        self.result = result
        self.activated = []
        self.deactivated = []

    def activate(self, target):
        self.activated.append(target)
        return self.result

    def deactivate(self, target):
        self.deactivated.append(target)
        return self.result


def test_feature_router_does_not_mask_activation_failure():
    router = FeatureCommandRouter()
    router.identity = FakeIdentity({
        "recognized": True,
        "command": "activate",
        "target": "terminal",
    })
    router.activation = FakeActivation({
        "success": False,
        "error": "feature_not_ready",
        "blockers": ["verified OS sandbox unavailable"],
    })

    result = router.process("Lumira activate terminal")

    assert result["success"] is False
    assert result["result"]["error"] == "feature_not_ready"
    assert router.activation.activated == ["terminal"]


def test_feature_router_reports_success_only_after_operation_succeeds():
    router = FeatureCommandRouter()
    router.identity = FakeIdentity({
        "recognized": True,
        "command": "disable",
        "target": "notepad",
    })
    router.activation = FakeActivation({"success": True, "status": "DISABLED"})

    result = router.process("Lumira disable notepad")

    assert result["success"] is True
    assert result["result"]["status"] == "DISABLED"
    assert router.activation.deactivated == ["notepad"]


def test_feature_router_rejects_unrecognized_command_without_mutation():
    router = FeatureCommandRouter()
    router.identity = FakeIdentity({"recognized": False})
    fake_activation = FakeActivation({"success": True})
    router.activation = fake_activation

    result = router.process("ordinary conversation")

    assert result["success"] is False
    assert result["type"] == "not_feature_command"
    assert fake_activation.activated == []
    assert fake_activation.deactivated == []


def test_feature_activation_accepts_human_readable_names(monkeypatch):
    from app.services.features.feature_activation_service import FeatureActivationService
    from app.services.features.feature_registry_service import FeatureRegistryService
    from app.services.providers.provider_registry import ProviderRegistry
    import tempfile
    from pathlib import Path

    monkeypatch.setattr(
        ProviderRegistry,
        "get",
        classmethod(lambda cls, name: object() if name == "image_generation" else None),
    )

    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        activation = FeatureActivationService(registry)

        assert activation.activate("artifact manager")["success"] is True
        result = activation.activate("image generation")
        assert result["success"] is True
        assert result["feature"] == "image_generation"
        status = activation.status("image-generation")
        assert status["success"] is True
        assert status["feature"] == "image_generation"
        deactivated = activation.deactivate("image generation")
        assert deactivated["success"] is True
        assert deactivated["feature"] == "image_generation"


def test_feature_activation_still_blocks_terminal_without_os_sandbox(tmp_path):
    from app.services.features.feature_activation_service import FeatureActivationService
    from app.services.features.feature_registry_service import FeatureRegistryService

    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    result = FeatureActivationService(registry).activate("terminal")

    assert result["success"] is False
    assert any("OS-level sandbox" in item for item in result["blockers"])
