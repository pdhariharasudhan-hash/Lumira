from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlparse

import requests

from app.services.devices.device_profile_service import DeviceProfileService


class LocalHttpDeviceTransport:
    """Opt-in local LAN JSON transport; never acts as a public network proxy."""
    provider_scope = "local"
    MAX_RESPONSE_BYTES = 16_384

    def __init__(self, profiles=None, timeout=(1.5, 3.0)):
        self.profiles = profiles or DeviceProfileService()
        self.timeout = timeout

    @staticmethod
    def _endpoint(value: object) -> str:
        if not isinstance(value, str) or len(value) > 240:
            raise ValueError("Device profile endpoint is missing or invalid")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Device endpoint must be an HTTP(S) URL without credentials, query or fragment")
        try:
            address = ipaddress.ip_address(parsed.hostname)
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError:
            raise ValueError("Device endpoint must use a literal private or loopback IP address and a valid port") from None
        if not (address.is_private or address.is_loopback) or address.is_multicast or address.is_unspecified or not 1 <= port <= 65535:
            raise ValueError("Device endpoint must use a private or loopback IP address")
        if parsed.path not in {"", "/"}:
            raise ValueError("Device endpoint base path must be empty")
        return value.rstrip("/")

    def is_device_configured(self, device_id: str, device_type: str) -> bool:
        profile = next((item for item in self.profiles.list() if item.get("profile_id") == device_id), None)
        if not isinstance(profile, dict) or profile.get("device_type") != device_type:
            return False
        metadata = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
        try:
            self._endpoint(metadata.get("endpoint"))
            return True
        except ValueError:
            return False

    def send_command(self, device_id: str, device_type: str, action: str, payload: dict) -> dict:
        profile = next((item for item in self.profiles.list() if item.get("profile_id") == device_id), None)
        if not isinstance(profile, dict) or profile.get("device_type") != device_type:
            return {"success": False, "code": "device_profile_missing"}
        metadata = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
        endpoint = self._endpoint(metadata.get("endpoint"))
        response = None
        try:
            response = requests.post(endpoint + "/command", json={"device_id": device_id, "device_type": device_type, "action": action, "payload": payload}, headers={"Accept": "application/json"}, timeout=self.timeout, allow_redirects=False, stream=True)
            response.raise_for_status()
            chunks, total = [], 0
            for chunk in response.iter_content(chunk_size=4096):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.MAX_RESPONSE_BYTES:
                    raise ValueError("Device response exceeded the response limit")
                chunks.append(chunk)
            result = json.loads(b"".join(chunks).decode("utf-8"))
        finally:
            if response is not None:
                response.close()
        if not isinstance(result, dict) or result.get("success") is not True:
            return {"success": False, "code": "device_command_rejected"}
        command_id = result.get("command_id")
        if not isinstance(command_id, str) or not command_id or len(command_id) > 128:
            return {"success": False, "code": "device_command_unconfirmed"}
        return {"success": True, "command_id": command_id, "transport": "local_http"}
