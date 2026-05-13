from __future__ import annotations

import logging
import secrets
import string
import time
from typing import Any

import httpx

from burnbox.exceptions import NoDomainsError, TokenError
from burnbox.models import InboxMessage, MessagePreview
from burnbox.providers.base import ProviderSession

import html2text

logger = logging.getLogger(__name__)

_SPECIAL = "!@#$%&*"
_PASSWORD_LEN = 16
_MIN_PASSWORD_LEN = 8


def _generate_secure_str(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _generate_password(length: int = _PASSWORD_LEN) -> str:
    if length < _MIN_PASSWORD_LEN:
        raise ValueError(f"Password length must be >= {_MIN_PASSWORD_LEN}, got {length}")
    while True:
        chars = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice(_SPECIAL),
        ]
        pool = string.ascii_letters + string.digits + _SPECIAL
        chars += [secrets.choice(pool) for _ in range(length - len(chars))]
        secrets.SystemRandom().shuffle(chars)
        password = "".join(chars)
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in _SPECIAL for c in password)
        ):
            return password


def _normalize_content(
    raw_html: str | list | None,
    raw_text: str | list | None,
    parser: html2text.HTML2Text,
) -> str:
    html_str = (
        "".join(str(i) for i in raw_html)
        if isinstance(raw_html, list)
        else (raw_html or "")
    )
    text_str = (
        "".join(str(i) for i in raw_text)
        if isinstance(raw_text, list)
        else (raw_text or "")
    )
    if html_str.strip():
        return parser.handle(html_str).strip()
    return text_str.strip() or "[Empty Message]"


def _make_html_parser() -> html2text.HTML2Text:
    parser = html2text.HTML2Text()
    parser.ignore_links = False
    parser.ignore_images = True
    parser.body_width = 0
    return parser


class MailTmProvider:
    name: str = "mailtm"
    supports_custom_url: bool = True

    def __init__(
        self,
        base_url: str = "https://api.mail.tm",
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._token: str | None = None
        self._account_id: str | None = None
        self._html_parser = _make_html_parser()

    async def _request(
        self,
        method: str,
        endpoint: str,
        body: dict | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{endpoint}"
        headers: dict[str, str] = {}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        response = await self._client.request(method, url, json=body, headers=headers)
        if response.status_code == 204:
            return {}
        response.raise_for_status()
        return response.json()

    async def is_alive(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/domains")
            return response.status_code == 200
        except Exception:
            return False

    async def register(self) -> ProviderSession:
        domains_data = await self._request("GET", "/domains", auth=False)
        members = domains_data.get("hydra:member", [])
        if not members:
            raise NoDomainsError("No domains available")

        domain = members[0]["domain"]
        address = f"{_generate_secure_str()}@{domain}"
        password = _generate_password()

        account_data = await self._request(
            "POST", "/accounts",
            body={"address": address, "password": password},
            auth=False,
        )
        account_id = account_data.get("id")

        token_data = await self._request(
            "POST", "/token",
            body={"address": address, "password": password},
            auth=False,
        )
        token = token_data.get("token")
        if not token:
            raise TokenError("Failed to retrieve authentication token")

        self._token = token
        self._account_id = account_id

        return ProviderSession(
            address=address,
            account_id=account_id,
            token=token,
            provider_name=self.name,
            created_at=time.time(),
        )

    async def login(self, address: str, password: str) -> ProviderSession:
        token_data = await self._request(
            "POST", "/token",
            body={"address": address, "password": password},
            auth=False,
        )
        token = token_data.get("token")
        if not token:
            raise TokenError("Failed to retrieve authentication token")
        self._token = token

        me = await self._request("GET", "/me")
        account_id = me.get("id")
        self._account_id = account_id

        return ProviderSession(
            address=address,
            account_id=account_id,
            token=token,
            provider_name=self.name,
            created_at=time.time(),
        )

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        data = await self._request("GET", "/messages")
        members = data.get("hydra:member", [])
        previews = [
            MessagePreview(
                id=m["id"],
                sender=m.get("from", {}).get("address", "Unknown Sender"),
                subject=m.get("subject", "No Subject"),
            )
            for m in members
        ]
        new = [p for p in previews if p.id not in seen_ids]

        messages: list[InboxMessage] = []
        for p in new:
            full = await self._request("GET", f"/messages/{p.id}")
            content = _normalize_content(
                full.get("html"), full.get("text"), self._html_parser
            )
            messages.append(InboxMessage(
                id=p.id,
                sender=p.sender,
                subject=p.subject,
                content=content,
            ))
        return messages

    async def delete_account(self, account_id: str) -> bool:
        try:
            await self._request("DELETE", f"/accounts/{account_id}")
            return True
        except Exception:
            logger.warning("Failed to delete account %s", account_id)
            return False
