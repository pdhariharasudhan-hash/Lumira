from app.main import app


def test_image_generation_route_is_registered():
    paths = {route.path for route in app.routes}
    assert "/images/generate" in paths


def test_image_generation_alias_uses_real_image_renderer(monkeypatch):
    from app.services.capabilities import capability_router_service as module

    class FakeImageService:
        def __init__(self):
            self.calls = []

        def generate(self, prompt, image_type):
            self.calls.append((prompt, image_type))
            return {"success": False, "code": "provider_unavailable"}

    class ReadyFeatures:
        def status(self, feature):
            assert feature == "image_generation"
            return {
                "success": True,
                "metadata": {"enabled": True},
                "can_enable": True,
                "blockers": [],
            }

    router = object.__new__(module.CapabilityRouterService)
    router.features = ReadyFeatures()
    router.images = FakeImageService()

    result = router.execute("image_generation", {"request": "rocket"})

    assert result["success"] is False
    assert result["code"] == "provider_unavailable"
    assert router.images.calls == [("rocket", "image")]
