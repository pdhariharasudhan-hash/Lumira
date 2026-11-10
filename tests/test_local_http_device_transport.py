import pytest

from app.services.providers.local_http_device_transport import LocalHttpDeviceTransport


class Profiles:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def list(self):
        return [{"profile_id": "esp32-1", "device_type": "esp32", "metadata": {"endpoint": self.endpoint}}]


@pytest.mark.parametrize("endpoint", [
    "https://example.com",
    "http://8.8.8.8",
    "http://192.168.1.4/path",
    "http://user:pass@192.168.1.4",
    "http://192.168.1.4?x=1",
])
def test_local_transport_rejects_nonlocal_or_ambiguous_endpoints(endpoint):
    with pytest.raises(ValueError):
        LocalHttpDeviceTransport._endpoint(endpoint)


def test_local_transport_accepts_private_literal_ip():
    assert LocalHttpDeviceTransport._endpoint("http://192.168.1.50") == "http://192.168.1.50"


def test_readiness_requires_matching_profile_and_safe_endpoint():
    adapter = LocalHttpDeviceTransport(Profiles("http://192.168.1.50"))
    assert adapter.is_device_configured("esp32-1", "esp32") is True
    assert adapter.is_device_configured("other", "esp32") is False
