from __future__ import annotations

import re

from burnbox.detectors.base import CodeMatch, MessageContext
from burnbox.detectors.i18n import CONTEXT_BOOST_WORDS

_ALPHANUMERIC_LABELED = re.compile(
    r"(?:recovery code|backup code|recovery key|backup key|restore code)"
    r"[:\s]*([A-Za-z0-9\-_]{4,32})",
    re.IGNORECASE,
)
_ALPHANUMERIC_GENERIC = re.compile(r"\b([A-Z0-9]{4,8}-[A-Z0-9]{4,8}(?:-[A-Z0-9]{4,8})+)\b")
_ALPHANUMERIC_SIMPLE = re.compile(r"\b([A-Z0-9]{6,12})\b")
_PROXIMITY = 80
_BASE_CONFIDENCE = 0.5
_LABELED_CONFIDENCE = 0.85
_GENERIC_CONFIDENCE = 0.4

_BOOST_FLAT: list[re.Pattern[str]] = []
for _lang, words in CONTEXT_BOOST_WORDS.items():
    for w in words:
        try:
            _BOOST_FLAT.append(re.compile(w, re.IGNORECASE))
        except re.error:
            continue


class AlphanumericOtpParser:
    name: str = "AlphanumericOtpParser"
    priority: int = 12

    def parse(self, text: str, context: MessageContext) -> list[CodeMatch]:
        matches: list[CodeMatch] = []
        seen_values: set[str] = set()
        lower_text = text.lower()

        for m in _ALPHANUMERIC_LABELED.finditer(text):
            value = m.group(1)
            if value not in seen_values:
                matches.append(CodeMatch(
                    value=value,
                    start=m.start(1),
                    end=m.end(1),
                    kind="alphanumeric_otp",
                    source_parser=self.name,
                    confidence=_LABELED_CONFIDENCE,
                ))
                seen_values.add(value)

        for m in _ALPHANUMERIC_GENERIC.finditer(text):
            value = m.group(1)
            if value not in seen_values:
                matches.append(CodeMatch(
                    value=value,
                    start=m.start(1),
                    end=m.end(1),
                    kind="alphanumeric_otp",
                    source_parser=self.name,
                    confidence=_BASE_CONFIDENCE,
                ))
                seen_values.add(value)

        for m in _ALPHANUMERIC_SIMPLE.finditer(text):
            value = m.group(1)
            if value not in seen_values:
                conf = _GENERIC_CONFIDENCE
                window_start = max(0, m.start() - _PROXIMITY)
                window_end = min(len(lower_text), m.end() + _PROXIMITY)
                window = lower_text[window_start:window_end]
                if any(p.search(window) for p in _BOOST_FLAT):
                    conf = _BASE_CONFIDENCE
                else:
                    continue
                matches.append(CodeMatch(
                    value=value,
                    start=m.start(1),
                    end=m.end(1),
                    kind="alphanumeric_otp",
                    source_parser=self.name,
                    confidence=conf,
                ))
                seen_values.add(value)

        return matches
