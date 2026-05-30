from __future__ import annotations

from typing import Protocol, runtime_checkable

from burnbox.models import InboxMessage, Session


@runtime_checkable
class Provider(Protocol):
    """Protocol that all email providers must implement.

    Lifecycle: register() → fetch_messages() → delete_account()
    Resume:     restore() → fetch_messages() → delete_account()
    Cleanup:    aclose() must be called when done (use async context manager).
    """

    name: str
    supports_custom_url: bool

    async def is_alive(self) -> bool:
        """Check if the provider API is reachable."""
        ...

    async def register(self) -> Session:
        """Create a new temporary email account. Returns session for restore()."""
        ...

    async def restore(self, session: Session) -> None:
        """Restore auth state from a saved session.

        Raises AuthExpiredError if the session is no longer valid.
        """
        ...

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        """Fetch new (unseen) messages. seen_ids tracks previously seen message IDs."""
        ...

    async def delete_account(self, account_id: str) -> bool:
        """Delete the account. Returns True if deletion succeeded or is best-effort
        (provider has no delete API; emails expire naturally)."""
        ...

    async def aclose(self) -> None:
        """Close the HTTP client and release resources."""
        ...
