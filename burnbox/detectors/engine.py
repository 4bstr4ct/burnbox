from __future__ import annotations

from burnbox.detectors.base import CodeMatch, CodeParser, LINK_PATTERN, MessageContext
from burnbox.detectors.parsers import (
    AlphanumericOtpParser,
    LabeledOtpParser,
    NumericOtpParser,
    ResetLinkParser,
    UrlCodeParser,
)


def _default_parsers() -> list[CodeParser]:
    return [
        UrlCodeParser(),
        LabeledOtpParser(),
        AlphanumericOtpParser(),
        ResetLinkParser(),
        NumericOtpParser(),
    ]


class ParserEngine:
    def __init__(self, parsers: list[CodeParser] | None = None) -> None:
        self._parsers = parsers or _default_parsers()

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
        return LINK_PATTERN.findall(text)
