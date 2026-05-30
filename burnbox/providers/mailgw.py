from __future__ import annotations

import httpx

from burnbox.providers.mailtm import MailTmProvider


class MailGwProvider(MailTmProvider):
    """Mail.gw provider — same API shape as mail.tm, different base URL."""

    name: str = "mailgw"
    supports_custom_url: bool = True

    def __init__(
        self,
        base_url: str = "https://api.mail.gw",
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        super().__init__(base_url=base_url, client=client, timeout=timeout)
