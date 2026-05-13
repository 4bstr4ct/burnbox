from __future__ import annotations

from dataclasses import dataclass, asdict


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
    password: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("password", None)
        return d
