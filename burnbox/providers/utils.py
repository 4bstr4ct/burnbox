from __future__ import annotations

import logging
import secrets
import string
from typing import TYPE_CHECKING

import html2text

from burnbox.exceptions import BurnBoxError
from burnbox.providers.registry import ProviderRegistry, select_provider as _registry_select

if TYPE_CHECKING:
    from burnbox.config import AppConfig
    from burnbox.providers.base import Provider

logger = logging.getLogger(__name__)


def generate_id(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def make_html_parser() -> html2text.HTML2Text:
    parser = html2text.HTML2Text()
    parser.ignore_links = False
    parser.ignore_images = True
    parser.body_width = 0
    return parser


def build_registry(custom_url: str | None = None) -> ProviderRegistry:
    from burnbox.providers.guerrillamail import GuerrillaMailProvider
    from burnbox.providers.mailtm import MailTmProvider
    from burnbox.providers.tempfastmail import TempFastMailProvider

    from burnbox.security import validate_url

    registry = ProviderRegistry()
    if custom_url:
        validated = validate_url(custom_url, label="custom_url")
        registry.register(TempFastMailProvider(base_url=validated))
        registry.register(MailTmProvider(base_url=validated))
    else:
        registry.register(TempFastMailProvider())
        registry.register(MailTmProvider())
    registry.register(GuerrillaMailProvider())
    registry.discover_plugins()
    return registry


async def select_provider(config: AppConfig) -> tuple[Provider, list[Provider]]:
    registry = build_registry(config.custom_url)
    all_providers = registry.all()
    provider = await _registry_select(all_providers, preferred=config.provider_default)
    if not provider:
        raise BurnBoxError("No available providers. Check your network.")
    unused = [p for p in all_providers if p is not provider]
    return provider, unused


def get_provider_by_name(config: AppConfig, name: str) -> tuple[Provider | None, list[Provider]]:
    registry = build_registry(config.custom_url)
    provider = registry.get(name)
    unused = [p for p in registry.all() if p is not provider] if provider else registry.all()
    return provider, unused


async def close_unused(unused: list[Provider]) -> None:
    for p in unused:
        try:
            await p.aclose()
        except Exception as exc:
            logger.debug("Ignoring close error for %s: %s", p.name, exc)
