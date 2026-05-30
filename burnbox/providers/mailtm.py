from __future__ import annotations

import asyncio
import html as _html
import logging
import secrets
import string
import time
from typing import Any

import html2text
import httpx

from burnbox.exceptions import APIError, NoDomainsError, TokenError
from burnbox.models import InboxMessage, MessagePreview, Session
from burnbox.providers.sanitize import safe_path_segment
from burnbox.retry import RetryConfig, raise_for_status, retry

logger = logging.getLogger(__name__)

_SPECIAL = "!@#$%&*"
_PASSWORD_LEN = 16
_MIN_PASSWORD_LEN = 8
_FETCH_CONCURRENCY = 5
_RETRY_CFG = RetryConfig()


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
    raw_html: str | list[object] | None,
    raw_text: str | list[object] | None,
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
        return _html.unescape(parser.handle(html_str).strip())
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
        body: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{endpoint}"
        headers: dict[str, str] = {}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        async def _do() -> dict[str, Any]:
            response = await self._client.request(method, url, json=body, headers=headers)
            if response.status_code == 204:
                return {}
            raise_for_status(response, _RETRY_CFG)
            try:
                return dict(response.json())
            except Exception as exc:
                raise APIError(0, f"Invalid JSON response: {exc}") from exc

        return await retry(_do, cfg=_RETRY_CFG)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> MailTmProvider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def is_alive(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/domains")
            return response.status_code == 200
        except Exception:
            return False

    async def register(self) -> Session:
        domains_data = await self._request("GET", "/domains", auth=False)
        members = domains_data.get("hydra:member", [])
        if not members:
            raise NoDomainsError("No domains available")

        domain = members[0].get("domain")
        if not domain:
            raise NoDomainsError("No domain name in API response")

        address = f"{_generate_secure_str()}@{domain}"
        password = _generate_password()

        account_data = await self._request(
            "POST", "/accounts",
            body={"address": address, "password": password},
            auth=False,
        )
        account_id = str(account_data.get("id", ""))

        try:
            token_data = await self._request(
                "POST", "/token",
                body={"address": address, "password": password},
                auth=False,
            )
        except APIError:
            try:
                await self._request("DELETE", f"/accounts/{safe_path_segment(account_id)}", auth=False)
            except Exception:
                logger.warning("Failed to clean up orphaned account %s", account_id)
            raise TokenError("Failed to retrieve authentication token")

        token = token_data.get("token")
        if not token:
            raise TokenError("Failed to retrieve authentication token")

        self._token = token
        self._account_id = account_id

        return Session(
            address=address,
            account_id=account_id,
            token=token,
            provider_name=self.name,
            created_at=time.time(),
        )

    async def restore(self, session: Session) -> None:
        self._token = session.token
        self._account_id = session.account_id

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        data = await self._request("GET", "/messages")
        members = data.get("hydra:member", [])
        previews = [
            MessagePreview(
                id=m.get("id", ""),
                sender=m.get("from", {}).get("address", "Unknown Sender"),
                subject=m.get("subject", "No Subject"),
            )
            for m in members
            if m.get("id")
        ]
        new = [p for p in previews if p.id not in seen_ids]

        sem = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def _fetch_one(p: MessagePreview) -> InboxMessage:
            async with sem:
                full = await self._request("GET", f"/messages/{safe_path_segment(p.id)}")
            content = _normalize_content(
                full.get("html"), full.get("text"), self._html_parser
            )
            return InboxMessage(
                id=p.id,
                sender=p.sender,
                subject=p.subject,
                content=content,
            )

        results = await asyncio.gather(
            *[_fetch_one(p) for p in new], return_exceptions=True
        )
        messages: list[InboxMessage] = []
        for p, r in zip(new, results):
            if isinstance(r, InboxMessage):
                messages.append(r)
            elif isinstance(r, Exception):
                logger.warning("Failed to fetch message %s: %s", p.id, r)
        return messages

    async def delete_account(self, account_id: str) -> bool:
        try:
            await self._request("DELETE", f"/accounts/{safe_path_segment(account_id)}")
            return True
        except Exception:
            logger.warning("Failed to delete account %s", account_id)
            return False
