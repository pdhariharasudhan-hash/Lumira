import asyncio
import socket

import httpcore
import pytest
import time

from app.services.web.web_resource_service import (
    WebResourceError,
    WebResourceService,
)


PUBLIC_ANSWER = [
    (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 0))
]


@pytest.mark.parametrize(
    "url",
    [
        "https://@example.com/resource",
        "https://example.com%2eattacker.test/resource",
        "https://example.com\\@attacker.test/resource",
        "http://127.1/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://0x7f.0.0.1/",
        "http://0177.0.0.1/",
    ],
)
def test_validate_url_rejects_ambiguous_authority_before_dns(monkeypatch, url):
    calls = []
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: calls.append((args, kwargs)) or PUBLIC_ANSWER,
    )

    with pytest.raises(WebResourceError):
        WebResourceService().validate_url(url)

    assert calls == []


@pytest.mark.parametrize(
    "address",
    [
        "0.0.0.0",
        "10.1.2.3",
        "100.64.0.1",
        "127.0.0.1",
        "169.254.169.254",
        "172.16.0.1",
        "192.168.1.1",
        "192.0.2.1",
        "198.18.0.1",
        "224.0.0.1",
        "255.255.255.255",
        "::",
        "::1",
        "::ffff:127.0.0.1",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "2002:7f00:1::1",
        "64:ff9b::a00:1",
        "64:ff9b:1::1",
    ],
)
def test_resolver_rejects_private_special_and_transition_addresses(monkeypatch, address):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 0, 0, 0) if family == socket.AF_INET6 else (address, 0))
        ],
    )

    with pytest.raises(WebResourceError):
        WebResourceService._resolve_public_addresses("example.com", 443)


def test_resolver_rejects_mixed_public_and_private_dns_answers(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.8", 0)),
        ],
    )

    with pytest.raises(WebResourceError):
        WebResourceService._resolve_public_addresses("example.com", 443)


def test_dns_resolution_is_bounded_by_the_connect_timeout(monkeypatch):
    from app.services.web.web_resource_service import _PublicAddressPinnedBackend

    connected = []

    def slow_resolver(*_args, **_kwargs):
        time.sleep(0.15)
        return PUBLIC_ANSWER

    async def fake_connect(self, host, port, timeout=None, local_address=None, socket_options=None):
        connected.append((host, port))
        return object()

    monkeypatch.setattr(socket, "getaddrinfo", slow_resolver)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", fake_connect)

    with pytest.raises(httpcore.ConnectTimeout):
        asyncio.run(_PublicAddressPinnedBackend().connect_tcp("example.com", 443, timeout=0.02))

    assert connected == []


def test_fetch_uses_the_pinned_transport_and_never_connects_to_private_dns(monkeypatch):
    from app.services.web.web_resource_service import _PublicAddressPinnedBackend

    connected = []
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.8", 443))
        ],
    )

    async def fake_connect(self, host, port, timeout=None, local_address=None, socket_options=None):
        connected.append((host, port))
        return object()

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", fake_connect)

    with pytest.raises(WebResourceError):
        asyncio.run(WebResourceService().fetch("https://example.com/resource"))

    assert connected == []


def test_pinned_backend_supports_public_ipv6_without_resolving_at_connect(monkeypatch):
    from app.services.web.web_resource_service import _PublicAddressPinnedBackend

    connected = []
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("2001:4860:4860::8888", 443, 0, 0))
        ],
    )

    async def fake_connect(self, host, port, timeout=None, local_address=None, socket_options=None):
        connected.append((host, port))
        return object()

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", fake_connect)
    result = asyncio.run(_PublicAddressPinnedBackend().connect_tcp("example.com", 443, timeout=1.0))

    assert result is not None
    assert connected == [("2001:4860:4860::8888", 443)]


def test_redirect_to_private_address_is_rejected_before_second_request(monkeypatch):
    requests = []
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: PUBLIC_ANSWER,
    )

    class FakeResponse:
        status_code = 302
        is_success = False
        headers = {"location": "http://127.0.0.1/admin"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url):
            requests.append((method, str(url)))
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.web.web_resource_service.httpx.AsyncClient",
        FakeClient,
    )

    with pytest.raises(WebResourceError):
        asyncio.run(WebResourceService().fetch("https://example.com/start"))

    assert requests == [("GET", "https://example.com/start")]


def test_pinned_transport_passes_backend_via_public_httpcore_constructor(monkeypatch):
    from app.services.web import web_resource_service as module

    captured = {}

    class CapturePool:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def aclose(self):
            return None

    monkeypatch.setattr(module.httpcore, "AsyncConnectionPool", CapturePool)

    transport = module._PinnedDNSHTTPTransport()

    assert "network_backend" in captured
    assert isinstance(captured["network_backend"], module._PublicAddressPinnedBackend)



def test_pinned_transport_preserves_hostname_and_closes_response_stream(monkeypatch):
    from types import SimpleNamespace
    from app.services.web import web_resource_service as module

    captured = {}

    class FakeResponseStream:
        async def __aiter__(self):
            yield b"safe response"

        async def aclose(self):
            captured["stream_closed"] = True

    class CapturePool:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def handle_async_request(self, request):
            captured["request_host"] = request.url.host
            captured["host_header"] = next(
                value for name, value in request.headers if name.lower() == b"host"
            )
            return SimpleNamespace(
                status=200,
                headers=[(b"content-type", b"text/plain")],
                extensions={},
                stream=FakeResponseStream(),
            )

        async def aclose(self):
            captured["pool_closed"] = True

    monkeypatch.setattr(module.httpcore, "AsyncConnectionPool", CapturePool)
    transport = module._PinnedDNSHTTPTransport()
    request = module.httpx.Request("GET", "https://example.com/resource")

    async def exercise_transport():
        response = await transport.handle_async_request(request)
        body = b"".join([chunk async for chunk in response.aiter_bytes()])
        await response.aclose()
        await transport.aclose()
        return response, body

    response, body = asyncio.run(exercise_transport())

    assert response.status_code == 200
    assert body == b"safe response"
    assert captured["request_host"] == b"example.com"
    assert captured["host_header"] == b"example.com"
    assert captured["stream_closed"] is True
    assert captured["pool_closed"] is True



def test_extracted_links_filter_multicast_translation_and_ambiguous_hosts():
    links = WebResourceService._safe_links(
        "https://example.com/",
        [
            "http://224.0.0.1/",
            "http://[ff02::1]/",
            "http://[64:ff9b::a00:1]/",
            "http://127.1/admin",
            "https://example.com%2eattacker.test/",
            "https://example.com\\@attacker.test/",
        ],
    )

    assert links == []
