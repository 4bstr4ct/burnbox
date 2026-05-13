import html2text

from burnbox.api import APIClient
from burnbox.models import InboxMessage, MessagePreview
from burnbox.schemas import extract_members


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


class MessageService:
    def __init__(self, api: APIClient) -> None:
        self._api = api
        self._html_parser = _make_html_parser()

    def list_previews(self) -> list[MessagePreview]:
        data = self._api.request("GET", "/messages")
        members = extract_members(data)
        return [
            MessagePreview(
                id=m["id"],
                sender=m.get("from", {}).get("address", "Unknown Sender"),
                subject=m.get("subject", "No Subject"),
            )
            for m in members
        ]

    def get_message(self, msg_id: str) -> InboxMessage:
        full = self._api.request("GET", f"/messages/{msg_id}")
        sender = full.get("from", {}).get("address", "Unknown Sender")
        subject = full.get("subject", "No Subject")
        content = _normalize_content(
            full.get("html"), full.get("text"), self._html_parser
        )
        return InboxMessage(
            id=msg_id, sender=sender, subject=subject, content=content
        )

    def fetch_new(self, seen_ids: set[str]) -> list[InboxMessage]:
        previews = self.list_previews()
        new = [p for p in previews if p.id not in seen_ids]
        return [self.get_message(p.id) for p in new]
