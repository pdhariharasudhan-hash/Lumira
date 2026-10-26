from __future__ import annotations

import ipaddress
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from app.services.artifacts.artifact_manager_service import ArtifactManagerService

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend


class WebResourceError(ValueError):
    """Raised when a web resource cannot be safely accessed."""


class _PublicAddressPinnedBackend(AutoBackend):
    """Resolve and validate a public address at connect time, then connect to that IP.

    The URL hostname remains unchanged in httpcore, so HTTP Host and TLS certificate/SNI
    validation continue to use the requested hostname while TCP connects to the pinned IP.
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        try:
            addresses = WebResourceService._resolve_public_addresses(host, port)
        except WebResourceError as exc:
            raise httpcore.ConnectError("Hostname did not resolve to a safe public address") from exc
        if not addresses:
            raise httpcore.ConnectError("Hostname did not resolve to a safe public address")
        last_error = None
        for address in addresses:
            try:
                return await super().connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, OSError) as exc:
                last_error = exc
        raise httpcore.ConnectError("Unable to connect to a validated public address") from last_error


class _PinnedDNSHTTPTransport(httpx.AsyncHTTPTransport):
    """HTTPX transport that prevents a second, unvalidated DNS lookup at connect time."""

    def __init__(self):
        super().__init__(trust_env=False, retries=0)
        # HTTPX 0.28.x constructs this pool for a direct transport (no proxy).
        # Fail closed if a future HTTPX/httpcore change alters the expected shape.
        if not isinstance(self._pool, httpcore.AsyncConnectionPool):
            raise RuntimeError("Pinned DNS transport requires a direct HTTP connection pool")
        self._pool._network_backend = _PublicAddressPinnedBackend()


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
    TIMEOUT = httpx.Timeout(15.0, connect=5.0)
    USER_AGENT = "Lumira/1.0 UniversalWebAccess"

    def __init__(self, artifact_manager: ArtifactManagerService | None = None):
        self.artifacts = artifact_manager or ArtifactManagerService()

    def validate_url(self, url: str) -> str:
        if not isinstance(url, str) or not url.strip():
            raise WebResourceError("A URL is required.")
        value = url.strip()
        if len(value) > 4096:
            raise WebResourceError("The URL exceeds Lumira's safe length limit.")
        try:
            parsed = urlsplit(value)
            # Accessing .port forces urllib to reject malformed/non-numeric ports.
            _ = parsed.port
        except ValueError as exc:
            raise WebResourceError("The URL is malformed.") from exc
        if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
            raise WebResourceError("Only HTTP and HTTPS URLs are allowed.")
        if parsed.username or parsed.password:
            raise WebResourceError("URLs containing credentials are not allowed.")
        if not parsed.hostname:
            raise WebResourceError("The URL must include a hostname.")
        self._validate_hostname(parsed.hostname)
        return value

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
            if address is not None and not address.is_global:
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
    def _resolve_public_addresses(hostname: str, port: int | None) -> list[str]:
        lowered = hostname.rstrip(".").lower()
        if lowered in {"localhost", "localhost.localdomain"}:
            raise WebResourceError("Localhost targets are not allowed.")
        try:
            records = socket.getaddrinfo(lowered, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise WebResourceError("The hostname could not be resolved safely.") from exc
        if not records:
            raise WebResourceError("The hostname did not resolve to a usable address.")

        public_addresses: list[str] = []
        seen: set[str] = set()
        for item in records:
            address = item[4][0]
            if address in seen:
                continue
            seen.add(address)
            try:
                ip = ipaddress.ip_address(address.split("%", 1)[0])
            except ValueError as exc:
                raise WebResourceError("The hostname resolved to an invalid network address.") from exc
            # Reject the whole answer if even one result is private or special-purpose.
            if not ip.is_global:
                raise WebResourceError("Private or special-purpose network targets are not allowed.")
            public_addresses.append(str(ip))
        return public_addresses

    def _validate_hostname(self, hostname: str) -> None:
        self._resolve_public_addresses(hostname, None)

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
                except httpx.HTTPError as exc:
                    # Avoid echoing request URLs, which may contain sensitive query parameters.
                    raise WebResourceError("Unable to access the requested resource.") from exc
