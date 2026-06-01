from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from burnbox.exceptions import BurnBoxError


def validate_url(url: str, label: str = "URL") -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise BurnBoxError(
            f"Invalid {label} scheme {parsed.scheme!r}: only https/http allowed"
        )
    if not parsed.hostname:
        raise BurnBoxError(f"Invalid {label}: no hostname in {url!r}")
    hostname = parsed.hostname
    if hostname in ("localhost", "127.0.0.1", "::1"):
        if parsed.scheme != "http":
            raise BurnBoxError(
                f"{label} points to loopback but uses {parsed.scheme!r}: use http://"
            )
        return url
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise BurnBoxError(
                f"{label} hostname {hostname!r} is a private/reserved address"
            )
    except ValueError:
        pass
    return url
