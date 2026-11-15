"""Safe host binding policy for Lumira's local desktop backend."""

from __future__ import annotations

import ipaddress


def validate_bind_host(host: str) -> str:
    """Accept explicit loopback names or addresses only.

    Remote binding has no authenticated remote bootstrap flow yet, so launch
    fails closed instead of exposing the backend when HOST is misconfigured.
    """
    if not isinstance(host, str) or not host or host != host.strip():
        raise ValueError("Lumira may bind only to a loopback host")

    if host.lower() == "localhost":
        return host

    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Lumira may bind only to a loopback host") from exc

    if not address.is_loopback:
        raise ValueError("Lumira may bind only to a loopback host")
    return host
