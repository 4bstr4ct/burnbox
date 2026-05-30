from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InboxMessage:
    id: str
    sender: str
    subject: str
    content: str


@dataclass(frozen=True)
class MessagePreview:
    id: str
    sender: str
    subject: str


@dataclass(frozen=True)
class Session:
    address: str
    account_id: str
    token: str
    provider_name: str
    created_at: float

    def __repr__(self) -> str:
        t = self.token
        masked = f"***({len(t)} chars)" if t else "(empty)"
        return (
            f"Session(address={self.address!r}, account_id={self.account_id!r}, "
            f"token={masked}, provider_name={self.provider_name!r}, "
            f"created_at={self.created_at!r})"
        )
