from __future__ import annotations

import logging
import secrets
import string
import time
from typing import Any

import html2text
import httpx

from burnbox.exceptions import APIError, AuthExpiredError
from burnbox.models import InboxMessage, Session
from burnbox.retry import RetryConfig, raise_for_status, retry

logger = logging.getLogger(__name__)

_RETRY_CFG = RetryConfig()


def _generate_login(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class OneSecMailProvider:
    """1secmail.com provider — simple REST API, no password, no account deletion.

    Emails expire naturally after ~1 hour. delete_account() is a no-op that
    returns True (best-effort: nothing to delete, inbox auto-expires).
    """

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
        async def _do() -> Any:
            response = await self._client.get(self._base_url, params=params)
            raise_for_status(response, _RETRY_CFG)
            try:
                return response.json()
            except Exception as exc:
                raise APIError(0, f"Invalid JSON response: {exc}") from exc

        return await retry(_do, cfg=_RETRY_CFG)

    async def is_alive(self) -> bool:
        try:
            response = await self._client.get(
                self._base_url, params={"action": "getDomainList"}
            )
            return response.status_code == 200
        except Exception:
            return False

    async def register(self) -> Session:
        login = _generate_login()
        domains_resp = await self._api(action="getDomainList")
        if not isinstance(domains_resp, list) or not domains_resp:
            raise APIError(0, "No domains available from 1secmail")
        domain = str(domains_resp[0])
        self._address = f"{login}@{domain}"
        self._login = login
        self._domain = domain

        return Session(
            address=self._address,
            account_id=self._address,
            token="",
            provider_name=self.name,
            created_at=time.time(),
        )

    async def restore(self, session: Session) -> None:
        if "@" not in session.address:
            raise AuthExpiredError(f"Invalid address format: {session.address!r}")
        login, domain = session.address.split("@", 1)
        self._address = session.address
        self._login = login
        self._domain = domain

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        if not self._login or not self._domain:
            raise AuthExpiredError("1secmail: not registered or restored")
        data = await self._api(
            action="getMessages", login=self._login, domain=self._domain
        )
        if not isinstance(data, list):
            return []
        new = [m for m in data if str(m.get("id", "")) not in seen_ids]

        messages: list[InboxMessage] = []
        for m in new:
            msg_id = str(m.get("id", ""))
            if not msg_id:
                continue
            full = await self._api(
                action="readMessage", login=self._login,
                domain=self._domain, id=msg_id,
            )
            body = full.get("body") or full.get("textBody") or "[Empty Message]"
            if full.get("htmlBody"):
                body = self._html_parser.handle(str(full["htmlBody"])).strip()
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
