from __future__ import annotations

import asyncio
import html as _html
import logging
import os
import time
from typing import Any

import httpx

from burnbox.exceptions import APIError, ProviderError
from burnbox.models import InboxMessage, Session
from burnbox.providers.sanitize import safe_path_segment
from burnbox.providers.utils import generate_id, make_html_parser
from burnbox.retry import RetryConfig, raise_for_status, retry

logger = logging.getLogger(__name__)

_API_BASE = os.environ.get("BURNBOX_GUERRILLA_URL", "https://api.guerrillamail.com/ajax.php")
_RETRY_CFG = RetryConfig()
_FETCH_CONCURRENCY = 5


class GuerrillaMailProvider:
    """Guerrilla Mail provider — JSON/AJAX API, no auth, cookie-based session.

    API docs: https://guerrillamail.com/dev/
    Domains: sharklasers.com, guerrillamail.com, grr.la, etc.
    Email lifetime: ~1 hour (extendable to ~2hr max).
    Session: sid_token ties requests to inbox; no password.
    """

    name: str = "guerrillamail"
    supports_custom_url: bool = False

    def __init__(
        self,
        base_url: str = _API_BASE,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._sid_token: str | None = None
        self._address: str | None = None
        self._html_parser = make_html_parser()

    async def _api(self, **params: Any) -> dict[str, Any]:
        async def _do() -> dict[str, Any]:
            response = await self._client.get(self._base_url, params=params)
            raise_for_status(response, _RETRY_CFG)
            try:
                data = response.json()
            except Exception as exc:
                raise APIError(0, f"Invalid JSON response: {exc}") from exc
            if not isinstance(data, dict):
                raise ProviderError(f"Unexpected API response type: {type(data).__name__}")
            return data

        return await retry(_do, cfg=_RETRY_CFG)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> GuerrillaMailProvider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def is_alive(self) -> bool:
        try:
            response = await self._client.get(self._base_url, params={"f": "get_email_address"})
            if response.status_code != 200:
                return False
            data = response.json()
            return "email_addr" in data
        except Exception:
            return False

    async def register(self) -> Session:
        data = await self._api(f="get_email_address")
        random_addr = data.get("email_addr", "")
        sid_token = data.get("sid_token", "")
        if not sid_token:
            raise ProviderError("Guerrilla Mail: failed to obtain sid_token")

        username = generate_id()
        data = await self._api(
            f="set_email_user",
            email_user=username,
            sid_token=sid_token,
        )
        address = data.get("email_addr", random_addr)
        self._sid_token = sid_token
        self._address = address

        return Session(
            address=address,
            account_id=sid_token,
            token=sid_token,
            provider_name=self.name,
            created_at=time.time(),
        )

    async def restore(self, session: Session) -> None:
        self._sid_token = session.token
        self._address = session.address

    _WELCOME_SENDER = "no-reply@guerrillamail.com"

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        if not self._sid_token:
            raise ProviderError("Guerrilla Mail: not registered or restored")
        data = await self._api(
            f="check_email",
            sid_token=self._sid_token,
            seq=0,
        )
        raw_list = data.get("list", [])

        to_fetch: list[tuple[str, str, str]] = []
        for m in raw_list:
            mail_id = str(m.get("mail_id", ""))
            if not mail_id or mail_id in seen_ids:
                continue

            sender = m.get("mail_from", "")
            if sender == self._WELCOME_SENDER:
                seen_ids.add(mail_id)
                continue

            to_fetch.append(
                (
                    mail_id,
                    sender,
                    m.get("mail_subject", "No Subject"),
                )
            )

        sem = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def _fetch_one(mid: str, sender: str, subject: str) -> InboxMessage:
            async with sem:
                full = await self._api(
                    f="fetch_email",
                    email_id=safe_path_segment(mid),
                    sid_token=self._sid_token,
                )

            body = full.get("mail_body", "")
            excerpt = full.get("mail_excerpt", "")
            if body.strip():
                if body != excerpt:
                    body = _html.unescape(self._html_parser.handle(body).strip())
            if not body:
                body = excerpt or "[Empty Message]"

            return InboxMessage(
                id=mid,
                sender=sender,
                subject=subject,
                content=body.strip() or "[Empty Message]",
            )

        results = await asyncio.gather(
            *[_fetch_one(mid, s, sub) for mid, s, sub in to_fetch],
            return_exceptions=True,
        )

        messages: list[InboxMessage] = []
        for (mid, s, sub), r in zip(to_fetch, results):
            if isinstance(r, InboxMessage):
                messages.append(r)
            elif isinstance(r, Exception):
                logger.warning("Failed to fetch message %s: %s", mid, r)
        return messages

    async def delete_account(self, account_id: str) -> bool:
        if not self._sid_token:
            return True
        try:
            response = await self._client.get(
                self._base_url,
                params={"f": "forget_me", "sid_token": self._sid_token},
            )
            response.raise_for_status()
            logger.info("Guerrilla Mail session forgotten (sid=%s...)", account_id[:8])
        except Exception as exc:
            logger.warning("Guerrilla Mail forget_me failed: %s", exc)
        return True
