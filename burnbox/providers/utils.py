from __future__ import annotations

import logging

from burnbox.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


def build_registry(custom_url: str | None = None) -> ProviderRegistry:
    from burnbox.providers.guerrillamail import GuerrillaMailProvider
    from burnbox.providers.mailgw import MailGwProvider
    from burnbox.providers.mailtm import MailTmProvider
    from burnbox.providers.onesecmail import OneSecMailProvider

    registry = ProviderRegistry()
    if custom_url:
        registry.register(MailTmProvider(base_url=custom_url))
    else:
        registry.register(MailTmProvider())
    registry.register(MailGwProvider())
    registry.register(OneSecMailProvider())
    registry.register(GuerrillaMailProvider())
    registry.discover_plugins()
    return registry
