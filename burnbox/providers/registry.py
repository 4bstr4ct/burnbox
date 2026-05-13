from __future__ import annotations

import asyncio
import logging
from typing import Sequence

from burnbox.providers.base import Provider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> Provider | None:
        return self._providers.get(name)

    def list_names(self) -> list[str]:
        return list(self._providers.keys())

    def all(self) -> list[Provider]:
        return list(self._providers.values())


async def select_provider(
    providers: Sequence[Provider],
    preferred: str | None = None,
) -> Provider | None:
    if preferred:
        for p in providers:
            if p.name == preferred:
                if await p.is_alive():
                    return p
                logger.warning("Preferred provider %s is not alive, trying fallback", preferred)
                break

    results = await asyncio.gather(
        *[p.is_alive() for p in providers], return_exceptions=True
    )
    for provider, alive in zip(providers, results):
        if isinstance(alive, Exception):
            logger.warning("Health check failed for %s: %s", provider.name, alive)
            continue
        if alive:
            logger.info("Selected provider: %s", provider.name)
            return provider

    return None
