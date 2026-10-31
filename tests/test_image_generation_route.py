from app.main import app


def test_image_generation_route_is_registered():
    paths = {route.path for route in app.routes}
    assert "/images/generate" in paths
