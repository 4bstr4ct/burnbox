from __future__ import annotations

import logging
import secrets
import string
import time
from typing import Any

import html2text
import httpx

from burnbox.models import InboxMessage
from burnbox.providers.base import ProviderSession

logger = logging.getLogger(__name__)


def _generate_login(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class OneSecMailProvider:
    """1secmail.com provider — simple REST API, no password, no account deletion."""

    name: str = "1secmail"
    supports_custom_url: bool = False

    def __init__(
        self,
        base_url: str = "https://www.1secmail.com/api/v1/",
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._address: str | None = None
        self._login: str | None = None
        self._domain: str | None = None
        self._html_parser = html2text.HTML2Text()
        self._html_parser.ignore_links = False
        self._html_parser.ignore_images = True
        self._html_parser.body_width = 0

    async def _api(self, **params: Any) -> Any:
        response = await self._client.get(self._base_url, params=params)
        response.raise_for_status()
        return response.json()

    async def is_alive(self) -> bool:
        try:
            response = await self._client.get(
                self._base_url, params={"action": "getDomainList"}
            )
            return response.status_code == 200
        except Exception:
            return False

    async def register(self) -> ProviderSession:
        login = _generate_login()
        domains_resp = await self._api(action="getDomainList")
        domain = domains_resp[0] if domains_resp else "1secmail.com"
        self._address = f"{login}@{domain}"
        self._login = login
        self._domain = domain

        return ProviderSession(
            address=self._address,
            account_id=self._address,
            token="",
            provider_name=self.name,
            created_at=time.time(),
        )

    async def login(self, address: str, password: str) -> ProviderSession:
        login, domain = address.split("@", 1)
        self._address = address
        self._login = login
        self._domain = domain
        return ProviderSession(
            address=address,
            account_id=address,
            token="",
            provider_name=self.name,
            created_at=time.time(),
        )

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        assert self._login and self._domain
        data = await self._api(
            action="getMessages", login=self._login, domain=self._domain
        )
        new = [m for m in data if str(m.get("id", "")) not in seen_ids]

        messages: list[InboxMessage] = []
        for m in new:
            msg_id = str(m["id"])
            full = await self._api(
                action="readMessage", login=self._login,
                domain=self._domain, id=msg_id,
            )
            body = full.get("body") or full.get("textBody") or "[Empty Message]"
            if full.get("htmlBody"):
                body = self._html_parser.handle(full["htmlBody"]).strip()
            messages.append(InboxMessage(
                id=msg_id,
                sender=m.get("from", ""),
                subject=m.get("subject", "No Subject"),
                content=body.strip() or "[Empty Message]",
            ))
        return messages

    async def delete_account(self, account_id: str) -> bool:
        return True

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> OneSecMailProvider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
