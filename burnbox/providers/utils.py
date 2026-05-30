from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

from burnbox.exceptions import BurnBoxError
from burnbox.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


def _validate_custom_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise BurnBoxError(
            f"Invalid custom_url scheme {parsed.scheme!r}: only https/http allowed"
        )
    if not parsed.hostname:
        raise BurnBoxError(f"Invalid custom_url: no hostname in {url!r}")
    hostname = parsed.hostname
    if hostname in ("localhost", "127.0.0.1", "::1"):
        if parsed.scheme != "http":
            raise BurnBoxError(
                f"custom_url points to loopback but uses {parsed.scheme!r}: use http://"
            )
        return url
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise BurnBoxError(
                f"custom_url hostname {hostname!r} is a private/reserved address"
            )
    except ValueError:
        pass
    return url


def build_registry(custom_url: str | None = None) -> ProviderRegistry:
    from burnbox.providers.guerrillamail import GuerrillaMailProvider
    from burnbox.providers.mailtm import MailTmProvider

    registry = ProviderRegistry()
    if custom_url:
        validated = _validate_custom_url(custom_url)
        registry.register(MailTmProvider(base_url=validated))
    else:
        registry.register(MailTmProvider())
    registry.register(GuerrillaMailProvider())
    registry.discover_plugins()
    return registry
