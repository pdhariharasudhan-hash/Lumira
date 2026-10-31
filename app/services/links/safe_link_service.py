from urllib.parse import urlparse
import ipaddress

class SafeLinkService:
    """Validate public HTTP(S) links without bypassing private access controls."""
    def validate(self, url):
        if not isinstance(url, str) or not url.strip() or len(url) > 2048:
            return {"safe": False, "code": "invalid_url"}
        parsed=urlparse(url.strip())
        if parsed.scheme not in {"http","https"} or not parsed.hostname:
            return {"safe": False, "code": "unsupported_scheme"}
        host=parsed.hostname.casefold()
        if host=="localhost" or host.endswith(".local"):
            return {"safe": False, "code": "private_host"}
        try:
            address=ipaddress.ip_address(host)
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
                return {"safe": False, "code": "private_host"}
        except ValueError:
            pass
        return {"safe": True, "url": url.strip(), "scheme": parsed.scheme, "host": host}
