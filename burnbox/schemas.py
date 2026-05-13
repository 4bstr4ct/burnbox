from typing import TypedDict


class DomainMember(TypedDict):
    domain: str


class AccountResponse(TypedDict, total=False):
    id: str
    address: str


class TokenResponse(TypedDict, total=False):
    token: str


class MessageSender(TypedDict, total=False):
    address: str


class MessageMember(TypedDict, total=False):
    id: str
    from_: MessageSender
    subject: str


class MessageDetailResponse(TypedDict, total=False):
    id: str
    from_: MessageSender
    subject: str
    html: str | list | None
    text: str | list | None


def extract_members(data: dict) -> list[dict]:
    return data.get("hydra:member", [])
