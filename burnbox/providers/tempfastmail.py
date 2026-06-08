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
from burnbox.providers.utils import make_html_parser
from burnbox.retry import RetryConfig, raise_for_status, retry

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = os.environ.get("BURNBOX_TEMPFASTMAIL_URL", "https://tempfastmail.com")
_RETRY_CFG = RetryConfig()
_FETCH_CONCURRENCY = 5


class TempFastMailProvider:
    name: str = "tempfastmail"
    supports_custom_url: bool = True

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._uuid: str | None = None
        self._html_parser = make_html_parser()

    async def _request(
        self,
        method: str,
        endpoint: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}{endpoint}"

        async def _do() -> Any:
            response = await self._client.request(method, url, json=body)
            raise_for_status(response, _RETRY_CFG)
            try:
                return response.json()
            except Exception as exc:
                raise APIError(0, f"Invalid JSON response: {exc}") from exc

        return await retry(_do, cfg=_RETRY_CFG)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> TempFastMailProvider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def is_alive(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/")
            return response.status_code == 200
        except Exception:
            return False

    async def register(self) -> Session:
        data = await self._request("POST", "/api/email-box", body={})
        if not isinstance(data, dict):
            raise ProviderError("TempFastMail: unexpected response type")
        email = data.get("email")
        uuid = data.get("uuid")
        if not email or not uuid:
            raise ProviderError("TempFastMail: missing email or uuid in response")
        self._uuid = uuid
        return Session(
            address=email,
            account_id=uuid,
            token=uuid,
            provider_name=self.name,
            created_at=time.time(),
        )

    async def restore(self, session: Session) -> None:
        self._uuid = session.account_id

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        if not self._uuid:
            raise ProviderError("TempFastMail: not registered or restored")
        box_uuid = self._uuid
        data = await self._request("GET", f"/api/email-box/{safe_path_segment(box_uuid)}/emails")
        if not isinstance(data, list):
            raise ProviderError("TempFastMail: expected list of emails")

        to_fetch = [
            m for m in data if isinstance(m, dict) and m.get("uuid") and m["uuid"] not in seen_ids
        ]

        sem = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def _fetch_one(item: dict[str, Any]) -> InboxMessage:
            email_uuid = str(item["uuid"])
            async with sem:
                full = await self._request(
                    "GET",
                    f"/api/email-box/{safe_path_segment(box_uuid)}"
                    f"/email/{safe_path_segment(email_uuid)}",
                )
            if not isinstance(full, dict):
                raise ProviderError("TempFastMail: expected email object")
            html_body = full.get("html") or ""
            text_body = full.get("text") or ""
            if html_body.strip():
                content = _html.unescape(self._html_parser.handle(html_body).strip())
            elif text_body.strip():
                content = text_body.strip()
            else:
                content = item.get("subject", "[Empty Message]")
            return InboxMessage(
                id=email_uuid,
                sender=item.get("from_name") or item.get("from", "Unknown Sender"),
                subject=item.get("subject", "No Subject"),
                content=content,
            )

        results = await asyncio.gather(*[_fetch_one(m) for m in to_fetch], return_exceptions=True)
        messages: list[InboxMessage] = []
        for m, r in zip(to_fetch, results):
            if isinstance(r, InboxMessage):
                messages.append(r)
            elif isinstance(r, Exception):
                logger.warning("Failed to fetch message %s: %s", m.get("uuid"), r)
        return messages

    async def delete_account(self, account_id: str) -> bool:
        logger.debug("TempFastMail: no delete API; emails auto-expire in 48h")
        return True
