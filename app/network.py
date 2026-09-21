from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def is_local_endpoint(url: str) -> bool:
    """Return True for loopback, private-address, link-local, or local hostnames."""
    host = (urlparse(url).hostname or "").lower()
    if host in {"localhost", "host.docker.internal"} or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local
