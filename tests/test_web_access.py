import asyncio
import socket
from fastapi.testclient import TestClient
from app.main import app
from app.services.web.web_resource_service import WebResourceError, WebResourceService


def test_validate_url_rejects_unsupported_scheme():
    service = WebResourceService()
    try:
        service.validate_url("file://local-resource")
    except WebResourceError as exc:
        assert "HTTP and HTTPS" in str(exc)
    else:
        raise AssertionError("unsupported scheme was accepted")


def test_validate_url_rejects_loopback(monkeypatch):
    service = WebResourceService()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))])
    try:
        service.validate_url("http://127.0.0.1:8000")
    except WebResourceError as exc:
        assert "Private or special-purpose" in str(exc)
    else:
        raise AssertionError("loopback target was accepted")


def test_web_route_is_registered():
    client = TestClient(app)
    assert "/web/fetch" in client.get("/openapi.json").json()["paths"]


def test_validate_url_rejects_credentials(monkeypatch):
    service = WebResourceService()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))])
    try:
        service.validate_url("https://user:pass@example.com")
    except WebResourceError as exc:
        assert "credentials" in str(exc)
    else:
        raise AssertionError("credential-bearing URL was accepted")


def test_fetch_text_resource_with_mock(monkeypatch):
    service = WebResourceService()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))])

    class FakeResponse:
        status_code = 200
        is_success = True
        headers = {"content-type": "text/plain; charset=utf-8"}
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def aiter_bytes(self):
            yield b"Lumira web access works."

    class FakeClient:
        def __init__(self, *args, **kwargs):
            assert kwargs.get("trust_env") is False
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        def stream(self, method, url):
            assert method == "GET"
            assert url == "https://example.com/test"
            return FakeResponse()

    monkeypatch.setattr("app.services.web.web_resource_service.httpx.AsyncClient", FakeClient)
    result = asyncio.run(service.fetch("https://example.com/test"))
    assert result["success"] is True
    assert result["content_type"] == "text/plain"
    assert result["text"] == "Lumira web access works."
    assert result["links"] == []
    assert result["artifact"] is None
    assert result["binary"] is False


def test_fetch_rejects_invalid_content_length(monkeypatch):
    service = WebResourceService()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))])

    class FakeResponse:
        status_code = 200
        is_success = True
        headers = {"content-type": "text/plain", "content-length": "not-a-number"}
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def aiter_bytes(self):
            yield b"small"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        def stream(self, method, url):
            return FakeResponse()

    monkeypatch.setattr("app.services.web.web_resource_service.httpx.AsyncClient", FakeClient)
    try:
        asyncio.run(service.fetch("https://example.com/test"))
    except WebResourceError as exc:
        assert "invalid content length" in str(exc)
    else:
        raise AssertionError("invalid Content-Length was accepted")


def test_fetch_enforces_actual_streamed_size_limit(monkeypatch):
    service = WebResourceService()
    service.MAX_BYTES = 4
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))])

    class FakeResponse:
        status_code = 200
        is_success = True
        headers = {"content-type": "text/plain"}
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def aiter_bytes(self):
            yield b"12345"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        def stream(self, method, url):
            return FakeResponse()

    monkeypatch.setattr("app.services.web.web_resource_service.httpx.AsyncClient", FakeClient)
    try:
        asyncio.run(service.fetch("https://example.com/test"))
    except WebResourceError as exc:
        assert "download limit" in str(exc)
    else:
        raise AssertionError("oversized streamed body was accepted")


def test_validate_url_rejects_malformed_ipv6_without_leaking_value_error():
    service = WebResourceService()
    try:
        service.validate_url("http://[::1")
    except WebResourceError as exc:
        assert "malformed" in str(exc)
    else:
        raise AssertionError("malformed IPv6 URL was accepted")


def test_validate_url_rejects_non_numeric_port(monkeypatch):
    service = WebResourceService()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))])
    try:
        service.validate_url("https://example.com:not-a-port")
    except WebResourceError as exc:
        assert "malformed" in str(exc)
    else:
        raise AssertionError("invalid port was accepted")


def test_validate_url_rejects_overlong_url_before_dns_lookup(monkeypatch):
    service = WebResourceService()
    called = {"dns": False}

    def unexpected_dns(*_args, **_kwargs):
        called["dns"] = True
        return []

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_dns)
    try:
        service.validate_url("https://example.com/" + "a" * 4100)
    except WebResourceError as exc:
        assert "length limit" in str(exc)
    else:
        raise AssertionError("overlong URL was accepted")
    assert called["dns"] is False



def test_safe_display_url_redacts_secret_query_values_and_fragments():
    safe = WebResourceService._safe_display_url(
        "https://example.com/resource?api_key=api-secret&topic=lumira"
        "&X-Amz-Signature=signed-secret&session_id=session-secret#fragment-secret"
    )

    assert "api-secret" not in safe
    assert "signed-secret" not in safe
    assert "session-secret" not in safe
    assert "fragment-secret" not in safe
    assert "topic=lumira" in safe
    assert "#" not in safe


def test_fetch_redacts_secret_query_values_from_response(monkeypatch):
    service = WebResourceService()
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )
    requested_url = (
        "https://example.com/test?api_key=provider-secret&topic=lumira"
        "#fragment-secret"
    )

    class FakeResponse:
        status_code = 200
        is_success = True
        headers = {"content-type": "text/plain"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aiter_bytes(self):
            yield b"safe response"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url):
            assert "provider-secret" in str(url)
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.web.web_resource_service.httpx.AsyncClient",
        FakeClient,
    )
    result = asyncio.run(service.fetch(requested_url))

    assert "provider-secret" not in str(result)
    assert "fragment-secret" not in str(result)
    assert "topic=lumira" in result["url"]
    assert "api_key=" in result["requested_url"]


def test_validate_url_rejects_hostname_with_no_resolved_addresses(monkeypatch):
    service = WebResourceService()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [])

    try:
        service.validate_url("https://example.com")
    except WebResourceError as exc:
        assert "did not resolve" in str(exc)
    else:
        raise AssertionError("hostname with no resolved addresses was accepted")


def test_validate_url_rejects_shared_non_global_address(monkeypatch):
    service = WebResourceService()
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.64.0.1", 0))
        ],
    )

    try:
        service.validate_url("https://example.com")
    except WebResourceError as exc:
        assert "Private or special-purpose" in str(exc)
    else:
        raise AssertionError("shared non-global address was accepted")


def test_safe_display_url_redacts_password_phrase_and_private_key_aliases():
    safe = WebResourceService._safe_display_url(
        "https://example.com/resource?passphrase=phrase-secret"
        "&private_key=private-secret&client_key=client-secret"
        "&access_key=access-secret&passcode=passcode-secret"
        "&pwd=pwd-secret&code=oauth-code-secret&compass=ordinary"
    )

    for secret in (
        "phrase-secret", "private-secret", "client-secret", "access-secret",
        "passcode-secret", "pwd-secret", "oauth-code-secret",
    ):
        assert secret not in safe
    assert "compass=ordinary" in safe



def test_safe_links_resolves_relative_urls_and_filters_unsafe_targets():
    safe = WebResourceService._safe_links(
        "https://example.com/articles/page",
        [
            "/related?api_key=secret#private-fragment",
            "https://docs.example.org/guide?topic=lumira",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "//localhost:8000/admin",
            "http://127.0.0.1:8000/",
            "http://127.1/admin",
            "http://2130706433/admin",
            "http://0x7f000001/admin",
            "http://0x7f.0.0.1/admin",
            "https://user:pass@example.org/private",
            "https://example.org:not-a-port/path",
            "mailto:someone@example.org",
            "https://docs.example.org/guide?topic=lumira",
        ],
    )

    assert safe == [
        "https://example.com/related?api_key=%5BREDACTED%5D",
        "https://docs.example.org/guide?topic=lumira",
    ]
    assert all("secret" not in url and "#" not in url for url in safe)


def test_safe_links_caps_output_and_deduplicates():
    links = ["https://example.org/page"] * 250

    safe = WebResourceService._safe_links("https://example.com/", links)

    assert safe == ["https://example.org/page"]



def test_fetch_does_not_persist_binary_artifact_for_http_error(monkeypatch):
    calls = []

    class FakeArtifacts:
        def create_binary_artifact(self, *args, **kwargs):
            calls.append((args, kwargs))
            return {"artifact_id": "should-not-exist"}

    service = WebResourceService(artifact_manager=FakeArtifacts())
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )

    class FakeResponse:
        status_code = 404
        is_success = False
        headers = {"content-type": "image/png"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aiter_bytes(self):
            yield b"not-a-real-image"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url):
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.web.web_resource_service.httpx.AsyncClient",
        FakeClient,
    )
    result = asyncio.run(service.fetch("https://example.com/not-found.png"))

    assert result["success"] is False
    assert result["artifact"] is None
    assert calls == []



def test_fetch_sanitizes_html_links_before_returning(monkeypatch):
    service = WebResourceService()
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )

    class FakeResponse:
        status_code = 200
        is_success = True
        headers = {"content-type": "text/html; charset=utf-8"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aiter_bytes(self):
            yield (
                b'<a href="/safe?api_key=hidden#fragment">safe</a>'
                b'<a href="javascript:alert(1)">unsafe</a>'
                b'<a href="https://user:pass@example.org/">credentials</a>'
                b'<a href="https://docs.example.org/guide">docs</a>'
            )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url):
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.web.web_resource_service.httpx.AsyncClient",
        FakeClient,
    )
    result = asyncio.run(service.fetch("https://example.com/article"))

    assert result["links"] == [
        "https://example.com/safe?api_key=%5BREDACTED%5D",
        "https://docs.example.org/guide",
    ]


def test_connect_time_dns_rebinding_is_blocked_before_socket_connect(monkeypatch):
    from app.services.web.web_resource_service import _PublicAddressPinnedBackend
    from httpcore._backends.auto import AutoBackend

    service = WebResourceService()
    answers = iter([
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))],
    ])
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: next(answers))
    service.validate_url("https://example.com/resource")

    connected = {"called": False}

    async def fake_connect(self, host, port, timeout=None, local_address=None, socket_options=None):
        connected["called"] = True
        return object()

    monkeypatch.setattr(AutoBackend, "connect_tcp", fake_connect)
    try:
        asyncio.run(_PublicAddressPinnedBackend().connect_tcp("example.com", 443))
    except Exception as exc:
        assert "safe public address" in str(exc)
    else:
        raise AssertionError("connect-time DNS rebinding was accepted")
    assert connected["called"] is False


def test_connect_uses_the_validated_public_ip_not_the_hostname(monkeypatch):
    from app.services.web.web_resource_service import _PublicAddressPinnedBackend
    from httpcore._backends.auto import AutoBackend

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )
    captured = {}

    async def fake_connect(self, host, port, timeout=None, local_address=None, socket_options=None):
        captured["host"] = host
        captured["port"] = port
        return object()

    monkeypatch.setattr(AutoBackend, "connect_tcp", fake_connect)
    result = asyncio.run(
        _PublicAddressPinnedBackend().connect_tcp("example.com", 443, timeout=3.0)
    )
    assert result is not None
    assert captured == {"host": "93.184.216.34", "port": 443}
