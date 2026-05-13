from __future__ import annotations

import asyncio
import logging
from importlib.metadata import entry_points
from typing import Sequence

from burnbox.providers.base import Provider

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "burnbox.providers"


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

    def discover_plugins(self) -> None:
        """Discover and register provider plugins via entry points."""
        eps = entry_points()
        # Python 3.12+ returns a SelectableGroups, <3.12 returns dict
        if hasattr(eps, "select"):
            group_eps = eps.select(group=_ENTRY_POINT_GROUP)
        else:
            group_eps = eps.get(_ENTRY_POINT_GROUP, [])

        for ep in group_eps:
            try:
                cls = ep.load()
                provider = cls()
                if isinstance(provider, Provider):
                    self.register(provider)
                    logger.info("Discovered plugin provider: %s", provider.name)
                else:
                    logger.warning(
                        "Plugin %s does not implement Provider protocol, skipping", ep.name
                    )
            except Exception as exc:
                logger.warning("Failed to load plugin %s: %s", ep.name, exc)


async def select_provider(
    providers: Sequence[Provider],
    preferred: str | None = None,
) -> Provider | None:
    if not providers:
        return None

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

    # Fallback: health checks are unreliable — try the first provider anyway.
    # Let the actual operation fail with a meaningful error if the provider is truly down.
    logger.warning("All health checks failed, falling back to %s", providers[0].name)
    return providers[0]
