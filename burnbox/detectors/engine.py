from __future__ import annotations

import re

from burnbox.detectors.base import CodeMatch, CodeParser, MessageContext
from burnbox.detectors.parsers import (
    AlphanumericOtpParser,
    LabeledOtpParser,
    NumericOtpParser,
    ResetLinkParser,
    UrlCodeParser,
)

_LINK_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def default_parsers() -> list[CodeParser]:
    return [
        UrlCodeParser(),
        LabeledOtpParser(),
        AlphanumericOtpParser(),
        ResetLinkParser(),
        NumericOtpParser(),
    ]


_EXPIRY_PATTERN = re.compile(
    r"(?:valid\s+for|expire[s]?\s+(?:in|after)?|expir(?:y|es)\s+(?:in|after)?|действителен|действует)"
    r"\s*"
    r"(\d+)\s*"
    r"(min(?:ute)?s?|hours?|hrs?|second?s?|sec|секунд|минут|часов|мин)",
    re.IGNORECASE,
)


class ParserEngine:
    def __init__(self, parsers: list[CodeParser] | None = None) -> None:
        self._parsers = parsers or default_parsers()

    def parse(self, text: str, context: MessageContext | None = None) -> list[CodeMatch]:
        ctx = context or MessageContext()
        all_matches: list[CodeMatch] = []
        seen_values: set[str] = set()
        for parser in sorted(self._parsers, key=lambda p: p.priority):
            matches = parser.parse(text, ctx)
            for m in matches:
                if m.value not in seen_values:
                    all_matches.append(m)
                    seen_values.add(m.value)
        return all_matches

    def best_code(self, matches: list[CodeMatch]) -> CodeMatch | None:
        if not matches:
            return None
        non_link = [m for m in matches if m.kind != "reset_link"]
        pool = non_link if non_link else matches
        if len(pool) == 1:
            return pool[0]
        return max(pool, key=lambda m: m.confidence)

    @staticmethod
    def detect_links(text: str) -> list[str]:
        return _LINK_PATTERN.findall(text)

    @staticmethod
    def detect_expiry(text: str) -> str | None:
        m = _EXPIRY_PATTERN.search(text)
        if m:
            return f"{m.group(1)} {m.group(2)}"
        return None
