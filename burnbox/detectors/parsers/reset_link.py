from __future__ import annotations

import re
from urllib.parse import urlparse

from burnbox.detectors.base import CodeMatch, LINK_PATTERN, MessageContext
from burnbox.detectors.i18n import RESET_PATH_SEGMENTS
_RESET_PATH_RE = re.compile(
    r"(?:/|^)(?:" + "|".join(re.escape(s) for s in RESET_PATH_SEGMENTS) + r")(?:/|$)",
    re.IGNORECASE,
)


class ResetLinkParser:
    name: str = "ResetLinkParser"
    priority: int = 15

    def __init__(self, confidence: float = 0.7) -> None:
        self._confidence = confidence

    def parse(self, text: str, context: MessageContext) -> list[CodeMatch]:
        matches: list[CodeMatch] = []
        seen_urls: set[str] = set()

        for m in LINK_PATTERN.finditer(text):
            url_str = m.group(0)
            if url_str in seen_urls:
                continue
            try:
                parsed = urlparse(url_str)
            except Exception:
                continue

            path = parsed.path.rstrip("/")
            if _RESET_PATH_RE.search(path):
                conf = self._confidence
                lower_subject = context.subject.lower()
                subject_hints = ["reset", "verify", "confirm", "activate", "unlock"]
                if any(h in lower_subject for h in subject_hints):
                    conf = min(conf + 0.1, 1.0)

                matches.append(CodeMatch(
                    value=url_str,
                    start=m.start(),
                    end=m.end(),
                    kind="reset_link",
                    source_parser=self.name,
                    confidence=conf,
                ))
                seen_urls.add(url_str)
        return matches
