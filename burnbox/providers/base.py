from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from burnbox.models import InboxMessage


@dataclass(frozen=True)
class ProviderSession:
    address: str
    account_id: str
    token: str
    provider_name: str
    created_at: float
    password: str | None = None


@runtime_checkable
class Provider(Protocol):
    name: str
    supports_custom_url: bool

    async def is_alive(self) -> bool: ...
    async def register(self) -> ProviderSession: ...
    async def login(self, address: str, password: str) -> ProviderSession: ...
    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]: ...
    async def delete_account(self, account_id: str) -> bool: ...
