from __future__ import annotations

import logging

from burnbox.config import AppConfig
from burnbox.detectors import copy_to_clipboard
from burnbox.exceptions import BurnBoxError, SessionError
from burnbox.models import InboxMessage, Session
from burnbox.providers.base import Provider, ProviderSession
from burnbox.session import SessionStore

logger = logging.getLogger(__name__)


class BurnBoxClient:
    def __init__(
        self,
        provider: Provider,
        session_store: SessionStore,
        config: AppConfig,
    ) -> None:
        self._provider = provider
        self._store = session_store
        self._config = config
        self._session: Session | None = None

    async def register(self) -> Session:
        ps: ProviderSession = await self._provider.register()
        session = Session(
            address=ps.address,
            account_id=ps.account_id,
            token=ps.token,
            provider_name=ps.provider_name,
            created_at=ps.created_at,
        )
        self._session = session
        self._store.save(session)
        if self._config.copy_address:
            copy_to_clipboard(session.address)
        return session

    async def resume(self) -> Session:
        session = self._store.load()
        if not session:
            raise SessionError("No saved session found. Run 'burnbox' first.")
        self._session = session
        # Verify token is still valid by trying to fetch
        try:
            await self._provider.fetch_messages(seen_ids=set())
        except Exception:
            self._store.delete()
            raise SessionError("Session expired. Start a new one with 'burnbox'.")
        return session

    async def fetch_new(self, seen_ids: set[str]) -> list[InboxMessage]:
        return await self._provider.fetch_messages(seen_ids)

    async def burn(self) -> bool:
        if not self._session:
            return False
        result = await self._provider.delete_account(self._session.account_id)
        if result:
            self._store.delete()
        return result

    @property
    def session(self) -> Session | None:
        return self._session
