from __future__ import annotations

import logging

from burnbox.config import AppConfig
from burnbox.exceptions import AuthExpiredError, SessionError
from burnbox.models import InboxMessage, Session
from burnbox.providers.base import Provider
from burnbox.session import SessionStore

logger = logging.getLogger(__name__)


class BurnBoxClient:
    """Core client orchestrating provider lifecycle.

    register() → fetch_new() → burn() is the normal flow.
    resume() → fetch_new() → burn() reconnects to a saved session.
    """

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
        """Create a new temp email account and save the session."""
        session = await self._provider.register()
        self._session = session
        self._store.save(session)
        return session

    async def resume(self) -> Session:
        """Restore a saved session. Raises SessionError if expired or missing."""
        session = self._store.load()
        if not session:
            raise SessionError("No saved session found. Run 'burnbox' first.")
        self._session = session
        await self._provider.restore(session)
        try:
            await self._provider.fetch_messages(seen_ids=set())
        except AuthExpiredError:
            self._store.delete()
            raise SessionError("Session expired. Start a new one with 'burnbox'.")
        return session

    async def fetch_new(self, seen_ids: set[str]) -> list[InboxMessage]:
        return await self._provider.fetch_messages(seen_ids)

    async def burn(self) -> bool:
        """Delete the account and session file. Returns True if successful."""
        if not self._session:
            return False
        result = await self._provider.delete_account(self._session.account_id)
        if result:
            self._store.delete()
        return result

    @property
    def session(self) -> Session | None:
        return self._session
