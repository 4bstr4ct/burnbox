from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import AsyncIterator

from burnbox.client import BurnBoxClient
from burnbox.config import AppConfig, load_config
from burnbox.detectors.base import CodeMatch, MessageContext
from burnbox.detectors.engine import ParserEngine
from burnbox.exceptions import AuthExpiredError, BurnBoxError
from burnbox.models import InboxMessage, Session
from burnbox.providers.base import Provider
from burnbox.providers.registry import select_provider
from burnbox.providers.utils import build_registry
from burnbox.session import SessionStore

logger = logging.getLogger(__name__)


async def _select(config: AppConfig) -> Provider:
    registry = build_registry(config.custom_url)
    all_providers = registry.all()
    provider = await select_provider(all_providers, preferred=config.provider_default)
    if not provider:
        for p in all_providers:
            try:
                await p.aclose()
            except Exception as exc:
                logger.debug("Ignoring close error for %s: %s", p.name, exc)
        raise RuntimeError("No available providers. Check your network.")
    for p in all_providers:
        if p is not provider:
            try:
                await p.aclose()
            except Exception as exc:
                logger.debug("Ignoring close error for %s: %s", p.name, exc)
    return provider


class Message:
    def __init__(self, inner: InboxMessage, engine: ParserEngine) -> None:
        self._inner = inner
        self._engine = engine
        self._codes: list[CodeMatch] | None = None

    @property
    def id(self) -> str:
        return self._inner.id

    @property
    def sender(self) -> str:
        return self._inner.sender

    @property
    def subject(self) -> str:
        return self._inner.subject

    @property
    def content(self) -> str:
        return self._inner.content

    @property
    def codes(self) -> list[CodeMatch]:
        if self._codes is None:
            ctx = MessageContext(sender=self.sender, subject=self.subject)
            self._codes = self._engine.parse(self.content, ctx)
        return self._codes

    @property
    def best_code(self) -> str | None:
        best = self._engine.best_code(self.codes)
        return best.value if best else None

    @property
    def links(self) -> list[str]:
        return self._engine.detect_links(self.content)


class BurnBox:
    """High-level async interface for temporary email.

    Usage::

        async with burnbox.create() as box:
            print(box.address)
            msg = await box.wait_for_message(timeout=60)
            if msg:
                print(msg.best_code)
    """

    def __init__(
        self,
        provider: Provider,
        client: BurnBoxClient,
        config: AppConfig,
        engine: ParserEngine | None = None,
    ) -> None:
        self._provider = provider
        self._client = client
        self._config = config
        self._engine = engine or ParserEngine()
        self._seen_ids: set[str] = set()

    @property
    def address(self) -> str | None:
        s = self._client.session
        return s.address if s else None

    @property
    def session(self) -> Session | None:
        return self._client.session

    async def fetch_new(self) -> list[Message]:
        raw = await self._client.fetch_new(self._seen_ids)
        messages = [Message(m, self._engine) for m in raw]
        for m in raw:
            self._seen_ids.add(m.id)
        return messages

    async def wait_for_message(self, timeout: float = 60.0) -> Message | None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            messages = await self.fetch_new()
            if messages:
                return messages[0]
            remaining = deadline - loop.time()
            if remaining <= 0:
                return None
            await asyncio.sleep(min(self._config.poll_interval, remaining))

    _MAX_CONSECUTIVE_ERRORS = 5

    async def messages(self, poll_interval: float | None = None) -> AsyncIterator[Message]:
        interval = poll_interval or self._config.poll_interval
        consecutive_errors = 0
        while True:
            try:
                new = await self.fetch_new()
                consecutive_errors = 0
                for m in new:
                    yield m
            except (AuthExpiredError, BurnBoxError):
                raise
            except Exception as exc:
                consecutive_errors += 1
                if consecutive_errors >= self._MAX_CONSECUTIVE_ERRORS:
                    raise BurnBoxError(
                        f"Too many consecutive errors ({consecutive_errors}). Last: {exc}"
                    ) from exc
            await asyncio.sleep(interval)

    async def burn(self) -> bool:
        return await self._client.burn()

    async def __aenter__(self) -> BurnBox:
        return self

    async def __aexit__(self, *args: object) -> None:
        try:
            await self.burn()
        except Exception as exc:
            logger.warning("Failed to burn account on exit: %s", exc)
        try:
            await self._provider.aclose()
        except Exception as exc:
            logger.warning("Failed to close provider on exit: %s", exc)


async def create(
    provider: str | None = None,
    config: AppConfig | None = None,
) -> BurnBox:
    cfg = config or load_config()
    if provider:
        cfg = replace(cfg, provider_default=provider)

    prov = await _select(cfg)
    store = SessionStore()
    client = BurnBoxClient(provider=prov, session_store=store, config=cfg)
    await client.register()
    return BurnBox(provider=prov, client=client, config=cfg)
