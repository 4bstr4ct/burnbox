from __future__ import annotations

import logging
import secrets
import string
import time
from typing import Any

import html2text
import httpx

from burnbox.exceptions import APIError, ProviderError
from burnbox.models import InboxMessage, Session
from burnbox.providers.sanitize import safe_path_segment
from burnbox.retry import RetryConfig, raise_for_status, retry

logger = logging.getLogger(__name__)

_API_BASE = "https://api.guerrillamail.com/ajax.php"
_RETRY_CFG = RetryConfig()


def _generate_username(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


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
        self._html_parser = html2text.HTML2Text()
        self._html_parser.ignore_links = False
        self._html_parser.ignore_images = True
        self._html_parser.body_width = 0

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
            data = await self._api(f="get_email_address")
            return "email_addr" in data
        except Exception:
            return False

    async def register(self) -> Session:
        data = await self._api(f="get_email_address")
        random_addr = data.get("email_addr", "")
        sid_token = data.get("sid_token", "")
        if not sid_token:
            raise ProviderError("Guerrilla Mail: failed to obtain sid_token")

        username = _generate_username()
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

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        if not self._sid_token:
            raise ProviderError("Guerrilla Mail: not registered or restored")
        data = await self._api(
            f="check_email",
            sid_token=self._sid_token,
            seq=0,
        )
        raw_list = data.get("list", [])
        messages: list[InboxMessage] = []

        for m in raw_list:
            mail_id = str(m.get("mail_id", ""))
            if not mail_id or mail_id in seen_ids:
                continue

            full = await self._api(
                f="fetch_email",
                email_id=safe_path_segment(mail_id),
                sid_token=self._sid_token,
            )

            body = full.get("mail_body", "")
            if "<" in body and ">" in body:
                body = self._html_parser.handle(body).strip()
            if not body:
                body = full.get("mail_excerpt", "") or "[Empty Message]"

            messages.append(InboxMessage(
                id=mail_id,
                sender=m.get("mail_from", "Unknown Sender"),
                subject=m.get("mail_subject", "No Subject"),
                content=body.strip() or "[Empty Message]",
            ))
        return messages

    async def delete_account(self, account_id: str) -> bool:
        try:
            data = await self._api(
                f="forget_me",
                sid_token=account_id,
                email_addr=self._address or "",
            )
            if isinstance(data, bool) and data:
                return True
            if isinstance(data, dict):
                return bool(data.get("success", False))
            return False
        except Exception:
            logger.warning("Guerrilla Mail: failed to forget address %s", self._address)
            return False
