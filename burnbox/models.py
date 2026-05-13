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
