from __future__ import annotations

import logging
import secrets
import string
import time
from typing import Any

import html2text
import httpx

from burnbox.exceptions import APIError, AuthExpiredError, NoDomainsError
from burnbox.models import InboxMessage, Session
from burnbox.retry import RetryConfig, raise_for_status, retry

logger = logging.getLogger(__name__)

_API_BASE = "https://dropmail.me/api/graphql/"
_DEFAULT_TOKEN = "web-test-1"
_RETRY_CFG = RetryConfig()


def _generate_login(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _make_html_parser() -> html2text.HTML2Text:
    parser = html2text.HTML2Text()
    parser.ignore_links = False
    parser.ignore_images = True
    parser.body_width = 0
    return parser


class DropMailProvider:
    """DropMail.me provider — GraphQL API with session-based inbox.

    API docs: https://dropmail.me/api/
    Domains: dropmail.me, 10mail.org, yomail.info, emlhub.com, etc.
    Session: sessions auto-expire after 10 min (extended on each access).
    Auth: free af_ token or legacy token for API access.
    Real-time: supports WebSocket subscriptions (not implemented here).
    """

    name: str = "dropmail"
    supports_custom_url: bool = False

    def __init__(
        self,
        api_token: str = _DEFAULT_TOKEN,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_token = api_token
        self._endpoint = f"{_API_BASE}{api_token}"
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._session_id: str | None = None
        self._address: str | None = None
        self._html_parser = _make_html_parser()

    async def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        async def _do() -> dict[str, Any]:
            response = await self._client.post(
                self._endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            raise_for_status(response, _RETRY_CFG)
            try:
                data = response.json()
            except Exception as exc:
                raise APIError(0, f"Invalid JSON response: {exc}") from exc

            if not isinstance(data, dict):
                raise APIError(0, f"Unexpected response type: {type(data).__name__}")

            errors = data.get("errors")
            if errors:
                blocking = [e for e in errors
                            if e.get("extensions", {}).get("code", "") != "LEGACY_TOKEN_DEPRECATED"]
                if blocking:
                    first = blocking[0]
                    code = first.get("extensions", {}).get("code", "")
                    msg = first.get("message", "Unknown GraphQL error")
                    if code == "SESSION_NOT_FOUND":
                        raise AuthExpiredError(f"DropMail session expired: {msg}")
                    raise APIError(0, f"DropMail GraphQL error ({code}): {msg}")

            result: dict[str, Any] = data.get("data", {})
            return result

        return await retry(_do, cfg=_RETRY_CFG)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> DropMailProvider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def is_alive(self) -> bool:
        try:
            data = await self._graphql("query { domains { id } }")
            return bool(data.get("domains"))
        except Exception:
            return False

    async def register(self) -> Session:
        data = await self._graphql(
            "mutation { introduceSession { id, expiresAt, addresses { address } } }"
        )
        session_data = data.get("introduceSession")
        if not session_data:
            raise APIError(0, "DropMail: failed to create session")

        self._session_id = str(session_data.get("id", ""))
        addresses = session_data.get("addresses", [])
        if not addresses:
            raise NoDomainsError("DropMail: no address returned")

        self._address = str(addresses[0].get("address", ""))

        return Session(
            address=self._address,
            account_id=self._session_id,
            token=self._session_id,
            provider_name=self.name,
            created_at=time.time(),
        )

    async def restore(self, session: Session) -> None:
        self._session_id = session.token
        self._address = session.address

    async def fetch_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        if not self._session_id:
            raise AuthExpiredError("DropMail: not registered or restored")

        data = await self._graphql(
            'query ($id: ID!) { session(id: $id) { mails { id, fromAddr, headerSubject, text, html } } }',
            variables={"id": self._session_id},
        )

        session_data = data.get("session")
        if session_data is None:
            raise AuthExpiredError("DropMail: session expired or not found")

        raw_mails = session_data.get("mails", [])
        messages: list[InboxMessage] = []

        for m in raw_mails:
            mail_id = str(m.get("id", ""))
            if not mail_id or mail_id in seen_ids:
                continue

            html_body = m.get("html")
            text_body = m.get("text")

            if html_body and str(html_body).strip():
                content = self._html_parser.handle(str(html_body)).strip()
            elif text_body and str(text_body).strip():
                content = str(text_body).strip()
            else:
                content = "[Empty Message]"

            messages.append(InboxMessage(
                id=mail_id,
                sender=m.get("fromAddr", "Unknown Sender"),
                subject=m.get("headerSubject", "No Subject"),
                content=content,
            ))
        return messages

    async def delete_account(self, account_id: str) -> bool:
        return True
