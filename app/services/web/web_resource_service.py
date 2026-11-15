from __future__ import annotations

import asyncio

import ipaddress
import re
import socket
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from app.services.artifacts.artifact_manager_service import ArtifactManagerService

import httpcore
import httpx


class WebResourceError(ValueError):
    """Raised when a web resource cannot be safely accessed."""


class _PublicAddressPinnedBackend(httpcore.AnyIOBackend):
    """Resolve and validate public addresses, then connect to a literal IP.

    The request URL keeps its hostname for HTTP Host and TLS SNI. The network
    backend receives only an IP literal after checking every DNS answer.
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        loop = asyncio.get_running_loop()
        connect_timeout = timeout if timeout is not None else WebResourceService.DNS_TIMEOUT
        deadline = loop.time() + max(0.0, connect_timeout)
        try:
            addresses = await WebResourceService._resolve_public_addresses_bounded(
                host, port, timeout=max(0.0, deadline - loop.time())
            )
        except WebResourceError as exc:
            raise httpcore.ConnectError("Hostname did not resolve to a safe public address") from exc
        if not addresses:
            raise httpcore.ConnectError("Hostname did not resolve to a safe public address")
        last_error = None
        for address in addresses:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise httpcore.ConnectTimeout("Connection deadline exceeded") from last_error
            try:
                return await super().connect_tcp(
                    address,
                    port,
                    timeout=remaining,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, OSError) as exc:
                last_error = exc
        raise httpcore.ConnectError("Unable to connect to a validated public address") from last_error


class _HTTPcoreAsyncByteStream(httpx.AsyncByteStream):
    """Adapt an HTTPcore response stream to HTTPX's public stream interface."""

    def __init__(self, stream):
        self._stream = stream

    async def __aiter__(self):
        async for chunk in self._stream:
            yield chunk

    async def aclose(self):
        await self._stream.aclose()


class _PinnedDNSHTTPTransport(httpx.AsyncBaseTransport):
    """HTTPX transport using HTTPcore's public network-backend injection point."""

    def __init__(self):
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=5.0,
            http1=True,
            http2=False,
            retries=0,
            network_backend=_PublicAddressPinnedBackend(),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        response = await self._pool.handle_async_request(core_request)
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=_HTTPcoreAsyncByteStream(response.stream),
            extensions=response.extensions,
        )

    async def aclose(self):
        await self._pool.aclose()


class _HTMLTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.links: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href and len(self.links) < 200:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)


class WebResourceService:
    ALLOWED_SCHEMES = {"http", "https"}
    MAX_BYTES = 10 * 1024 * 1024
    MAX_REDIRECTS = 5
    DNS_TIMEOUT = 3.0
    TIMEOUT = httpx.Timeout(15.0, connect=5.0)
    USER_AGENT = "Lumira/1.0 UniversalWebAccess"

    def __init__(self, artifact_manager: ArtifactManagerService | None = None):
        self.artifacts = artifact_manager or ArtifactManagerService()

    def validate_url(self, url: str) -> str:
        if not isinstance(url, str) or not url.strip():
            raise WebResourceError("A URL is required.")
        if len(url) > 4096:
            raise WebResourceError("The URL exceeds Lumira's safe length limit.")
        if url != url.strip() or any(
            character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
            for character in url
        ):
            raise WebResourceError("The URL is malformed.")
        try:
            parsed = urlsplit(url)
            # Accessing .port forces urllib to reject malformed/non-numeric ports.
            _ = parsed.port
            request_url = httpx.URL(url)
        except (ValueError, httpx.InvalidURL) as exc:
            raise WebResourceError("The URL is malformed.") from exc
        if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
            raise WebResourceError("Only HTTP and HTTPS URLs are allowed.")
        if "@" in parsed.netloc or parsed.username is not None or parsed.password is not None:
            raise WebResourceError("URLs containing credentials are not allowed.")
        if "%" in parsed.netloc or "\\" in parsed.netloc:
            raise WebResourceError("The URL authority is malformed.")
        if not parsed.hostname or not request_url.host:
            raise WebResourceError("The URL must include a hostname.")

        try:
            urllib_host = parsed.hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise WebResourceError("The URL hostname is malformed.") from exc
        transport_host = request_url.host.lower()
        if urllib_host.rstrip(".") != transport_host.rstrip("."):
            raise WebResourceError("The URL hostname is ambiguous.")

        self._validate_hostname(transport_host)
        # Return exactly the normalized URL whose host was validated and that
        # HTTPX will send, preventing parser differentials between validation
        # and transport.
        return str(request_url)

    @staticmethod
    def _safe_display_url(url: str) -> str:
        """Remove secret query values and fragments before persistence or display."""
        try:
            parsed = urlsplit(url)
            safe_query = []
            for key, value in parse_qsl(parsed.query, keep_blank_values=True):
                normalized_key = re.sub(r"[^a-z0-9]", "", key.casefold())
                sensitive = (
                    any(marker in normalized_key for marker in (
                        "password",
                        "secret",
                        "token",
                        "signature",
                        "credential",
                        "authorization",
                        "accesskeyid",
                    ))
                    or normalized_key in {
                        "apikey", "auth", "key", "sig", "session", "sessionid",
                        "pass", "passwd", "passphrase", "passcode", "pwd",
                        "privatekey", "clientkey", "accesskey", "secretkey",
                        "code", "authcode", "authorizationcode",
                    }
                )
                safe_query.append((key, "[REDACTED]" if sensitive else value))
            return urlunsplit((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(safe_query, doseq=True),
                "",
            ))
        except (TypeError, ValueError):
            return "[invalid-url]"

    @classmethod
    def _safe_links(cls, base_url: str, links: list[str]) -> list[str]:
        """Return bounded, credential-free HTTP(S) links suitable for display."""
        safe: list[str] = []
        seen: set[str] = set()
        for link in links[:200]:
            if not isinstance(link, str) or not link.strip() or len(link) > 4096:
                continue
            try:
                parsed = urlsplit(urljoin(base_url, link.strip()))
                _ = parsed.port
            except ValueError:
                continue

            hostname = (parsed.hostname or "").rstrip(".").lower()
            if (
                parsed.scheme.lower() not in cls.ALLOWED_SCHEMES
                or not hostname
                or "@" in parsed.netloc
                or "%" in parsed.netloc
                or "\\" in parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or hostname in {"localhost", "localhost.localdomain"}
                or hostname.endswith((".localhost", ".local", ".internal", ".test"))
            ):
                continue

            try:
                address = ipaddress.ip_address(hostname)
            except ValueError:
                address = None
            if address is not None and not cls._is_safe_public_address(address):
                continue
            # Browsers and URL stacks may interpret legacy numeric host forms
            # such as 127.1, 2130706433, or 0x7f000001 as IPv4 addresses.
            if address is None and re.fullmatch(
                r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*",
                hostname,
                re.IGNORECASE,
            ):
                continue

            absolute = urlunsplit((
                parsed.scheme.lower(),
                parsed.netloc,
                parsed.path,
                parsed.query,
                "",
            ))
            display_url = cls._safe_display_url(absolute)
            if display_url != "[invalid-url]" and display_url not in seen:
                seen.add(display_url)
                safe.append(display_url)
        return safe

    @staticmethod
    def _is_safe_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        if (
            not address.is_global
            or address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            return False
        if isinstance(address, ipaddress.IPv6Address):
            # These translation/tunneling forms can carry private IPv4 targets
            # through an otherwise globally classified IPv6 address.
            if address.ipv4_mapped is not None or address.sixtofour is not None or address.teredo is not None:
                return False
            if address in ipaddress.IPv6Network("64:ff9b::/96"):
                return False
            if address in ipaddress.IPv6Network("64:ff9b:1::/48"):
                return False
        return True

    @staticmethod
    def _normalize_hostname(
        hostname: str,
    ) -> tuple[str, ipaddress.IPv4Address | ipaddress.IPv6Address | None]:
        """Validate a host without doing blocking DNS on the request thread."""
        if not isinstance(hostname, str) or not hostname or hostname.endswith(".."):
            raise WebResourceError("The hostname is malformed.")
        lowered = hostname[:-1].lower() if hostname.endswith(".") else hostname.lower()
        if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(
            (".localhost", ".local", ".internal", ".test", ".invalid")
        ):
            raise WebResourceError("Local network hostnames are not allowed.")

        try:
            literal = ipaddress.ip_address(lowered)
        except ValueError:
            literal = None
        if literal is not None:
            if not WebResourceService._is_safe_public_address(literal):
                raise WebResourceError("Private or special-purpose network targets are not allowed.")
            return str(literal), literal

        if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", lowered, re.IGNORECASE):
            raise WebResourceError("Non-canonical IP address forms are not allowed.")
        try:
            ascii_hostname = lowered.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise WebResourceError("The hostname is malformed.") from exc
        labels = ascii_hostname.split(".")
        label_pattern = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)
        if (
            len(ascii_hostname) > 253
            or len(labels) < 2
            or any(not label or len(label) > 63 or not label_pattern.fullmatch(label) for label in labels)
        ):
            raise WebResourceError("A fully qualified DNS hostname is required.")
        return ascii_hostname, None

    @staticmethod
    def _resolve_public_addresses(hostname: str, port: int | None) -> list[str]:
        ascii_hostname, literal = WebResourceService._normalize_hostname(hostname)
        if literal is not None:
            return [str(literal)]

        try:
            # The final dot prevents resolver search-domain expansion to a
            # machine-local hostname.
            records = socket.getaddrinfo(ascii_hostname + ".", port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise WebResourceError("The hostname could not be resolved safely.") from exc
        if not records:
            raise WebResourceError("The hostname did not resolve to a usable address.")

        public_addresses: list[str] = []
        seen: set[str] = set()
        for item in records:
            address = item[4][0]
            if not isinstance(address, str) or "%" in address:
                raise WebResourceError("The hostname resolved to an invalid network address.")
            try:
                ip = ipaddress.ip_address(address)
            except ValueError as exc:
                raise WebResourceError("The hostname resolved to an invalid network address.") from exc
            canonical_address = str(ip)
            if canonical_address in seen:
                continue
            seen.add(canonical_address)
            # Reject the whole answer if even one result is private, special,
            # multicast, reserved, or can encode a private IPv4 destination.
            if not WebResourceService._is_safe_public_address(ip):
                raise WebResourceError("Private or special-purpose network targets are not allowed.")
            public_addresses.append(canonical_address)
        return public_addresses

    def _validate_hostname(self, hostname: str) -> None:
        self._normalize_hostname(hostname)

    @classmethod
    async def _resolve_public_addresses_bounded(
        cls, hostname: str, port: int | None, *, timeout: float
    ) -> list[str]:
        """Bound OS name resolution so it cannot bypass the connection timeout."""
        bounded_timeout = min(cls.DNS_TIMEOUT, max(0.0, timeout))
        if bounded_timeout <= 0:
            raise httpcore.ConnectTimeout("DNS resolution exceeded the connection deadline")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(cls._resolve_public_addresses, hostname, port),
                timeout=bounded_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise httpcore.ConnectTimeout("DNS resolution exceeded the connection deadline") from exc

    def _validate_redirect(self, current_url: str, location: str) -> str:
        return self.validate_url(urljoin(current_url, location))

    @staticmethod
    def _content_type(response: httpx.Response) -> str:
        return response.headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip().lower()

    @staticmethod
    def _extract_text(body: bytes, content_type: str) -> tuple[str | None, list[str]]:
        text = body.decode("utf-8", errors="replace") if (
            content_type.startswith("text/")
            or content_type in {"application/json", "application/xml", "application/javascript", "application/x-javascript"}
        ) else None
        if content_type == "text/html" and text is not None:
            parser = _HTMLTextParser()
            parser.feed(text)
            return " ".join(parser.parts), parser.links
        return text, []

    @staticmethod
    def _extension_for(content_type: str) -> str | None:
        return {
            "application/pdf": "pdf",
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/webp": "webp",
            "audio/mpeg": "mp3",
            "audio/wav": "wav",
            "audio/ogg": "ogg",
            "audio/mp4": "m4a",
            "video/mp4": "mp4",
            "video/webm": "webm",
        }.get(content_type)

    @staticmethod
    def _artifact_type_for(content_type: str) -> str | None:
        if content_type == "application/pdf":
            return "pdf"
        if content_type.startswith("image/"):
            return "images"
        if content_type.startswith("audio/"):
            return "audio"
        if content_type.startswith("video/"):
            return "video"
        return None

    async def fetch(self, url: str) -> dict:
        current = self.validate_url(url)
        redirects = 0
        async with httpx.AsyncClient(
            timeout=self.TIMEOUT,
            follow_redirects=False,
            trust_env=False,
            transport=_PinnedDNSHTTPTransport(),
            headers={"User-Agent": self.USER_AGENT, "Accept": "*/*"},
        ) as client:
            while True:
                self.validate_url(current)
                try:
                    async with client.stream("GET", current) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            if redirects >= self.MAX_REDIRECTS:
                                raise WebResourceError("The redirect limit was exceeded.")
                            location = response.headers.get("location")
                            if not location:
                                raise WebResourceError("The server returned an invalid redirect.")
                            current = self._validate_redirect(current, location)
                            redirects += 1
                            continue
                        content_length = response.headers.get("content-length")
                        if content_length is not None:
                            try:
                                declared_length = int(content_length)
                            except (TypeError, ValueError) as exc:
                                raise WebResourceError("The server returned an invalid content length.") from exc
                            if declared_length < 0:
                                raise WebResourceError("The server returned an invalid content length.")
                            if declared_length > self.MAX_BYTES:
                                raise WebResourceError("The resource is larger than Lumira's safe download limit.")
                        chunks: list[bytes] = []
                        total = 0
                        async for chunk in response.aiter_bytes():
                            total += len(chunk)
                            if total > self.MAX_BYTES:
                                raise WebResourceError("The resource exceeded Lumira's safe download limit.")
                            chunks.append(chunk)
                        body = b"".join(chunks)
                        content_type = self._content_type(response)
                        text, links = self._extract_text(body, content_type)
                        links = self._safe_links(current, links)
                        artifact = None
                        artifact_type = self._artifact_type_for(content_type)
                        extension = self._extension_for(content_type)
                        if response.is_success and artifact_type and extension:
                            try:
                                artifact = self.artifacts.create_binary_artifact(
                                    artifact_type,
                                    body,
                                    source=self._safe_display_url(current),
                                    extension=extension,
                                )
                            except ValueError:
                                artifact = None
                        return {
                            "success": response.is_success,
                            "url": self._safe_display_url(current),
                            "requested_url": self._safe_display_url(url),
                            "status_code": response.status_code,
                            "content_type": content_type,
                            "content_length": len(body),
                            "redirects": redirects,
                            "text": text,
                            "links": links,
                            "artifact": artifact,
                            "retrieved_at": datetime.now(timezone.utc).isoformat(),
                            "binary": text is None,
                        }
                except (httpx.HTTPError, httpcore.NetworkError, httpcore.TimeoutException, httpcore.ProtocolError, httpcore.ProxyError) as exc:
                    # Avoid echoing request URLs, which may contain sensitive query parameters.
                    raise WebResourceError("Unable to access the requested resource.") from exc
